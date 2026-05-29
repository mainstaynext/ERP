from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError
from datetime import date
from markupsafe import Markup

class ProjectTask(models.Model):
    _inherit = 'project.task'

    # ----- Custom subtask stage fields -----
    subtask_stage_id = fields.Many2one(
        'project.subtask.stage',
        string='Subtask Stage',
        domain="[('id', 'in', allowed_subtask_stage_ids)]",
        help='Stage for subtasks (only applicable if this task is a subtask)'
    )

    allowed_subtask_stage_ids = fields.Many2many(
        'project.subtask.stage',
        compute='_compute_allowed_subtask_stage_ids',
        help='Technical field to restrict stages based on user rights'
    )

    submission_comment = fields.Text('Submission Comment', readonly=True)
    submission_document_link = fields.Char('Supporting Document (SharePoint Link)', readonly=True)
    submitted_by = fields.Many2one('res.users', string='Submitted By', readonly=True)
    submitted_on = fields.Datetime('Submitted On', readonly=True)

    # ----- Planned start/end dates -----
    planned_start_date = fields.Date(string='Start Date')
    planned_end_date = fields.Date(string='End Date')

    # ----- Actual start/end dates -----
    actual_start_date = fields.Date(string='Actual Start Date')
    actual_end_date = fields.Date(string='Actual End Date')

    # ----- Other Custom Fields -----
    owner = fields.Char(string='Owner')
    module_name = fields.Many2one(
        'project.task.module',
        string='Module',
    )
    deliverables = fields.Char(string='Deliverables')
    client_responsibilities = fields.Char(string='Client Responsibilities')

    # ----- Consultant readonly helper -----
    is_project_consultant = fields.Boolean(
        compute='_compute_is_project_consultant',
    )

    def _compute_is_project_consultant(self):
        is_consultant = self.env.user.has_group(
            'project_mainstaypeopleconsulting.group_project_consultant'
        )
        for task in self:
            task.is_project_consultant = is_consultant

    # ----- Delay Status Field -----
    delay_status = fields.Selection(
        selection=[
            ('on_time', 'On Time'),
            ('delayed', 'Delayed'),
        ],
        string='Delay Status',
        compute='_compute_delay_status',
        store=True,  # stored for fast search/filter
    )
    # ----- Delay Duration -----
    delay_days = fields.Integer(
        string='Delay (Days)',
        compute='_compute_delay_days',
        store=True,
    )

    @api.depends('planned_start_date', 'planned_end_date',
                 'actual_start_date', 'actual_end_date',
                 'state', 'subtask_stage_id')
    def _compute_delay_status(self):
        today = date.today()
        for task in self:
            status = 'on_time'

            # Case: Subtask stage is 'On Hold' → Delayed
            if task.subtask_stage_id and task.subtask_stage_id.name == 'On-Hold':
                status = 'delayed'

            # Case: Task completed
            elif task.state == '1_done':
                if task.planned_end_date and task.actual_end_date:
                    if task.planned_end_date >= task.actual_end_date:
                        status = 'on_time'
                    else:
                        status = 'delayed'
                else:
                    status = 'on_time'

            # Case: Task not completed
            else:
                # 1. Planned start date in future → on time
                if task.planned_start_date and task.planned_start_date > today:
                    status = 'on_time'
                # 2. Actual start date is later than planned start → delayed
                elif (task.planned_start_date and task.actual_start_date and
                      task.actual_start_date > task.planned_start_date):
                    status = 'delayed'
                # 3. Planned end date already passed → delayed
                elif task.planned_end_date and task.planned_end_date < today:
                    status = 'delayed'
                else:
                    status = 'on_time'

            task.delay_status = status

    @api.depends(
        'planned_start_date',
        'planned_end_date',
        'actual_start_date',
        'actual_end_date',
        'state',
        'subtask_stage_id'
    )
    def _compute_delay_days(self):
        today = date.today()

        for task in self:
            delay = 0

            # On Hold → calculate from planned end date till today
            if (
                    task.subtask_stage_id
                    and task.subtask_stage_id.name == 'On-Hold'
                    and task.planned_end_date
                    and today > task.planned_end_date
            ):
                delay = (today - task.planned_end_date).days

            # Completed tasks
            elif task.state == '1_done':
                if task.planned_end_date and task.actual_end_date:
                    if task.actual_end_date > task.planned_end_date:
                        delay = (
                                task.actual_end_date
                                - task.planned_end_date
                        ).days

            # Incomplete tasks
            else:
                # Late start
                if (
                        task.planned_start_date
                        and task.actual_start_date
                        and task.actual_start_date > task.planned_start_date
                ):
                    delay = (
                            task.actual_start_date
                            - task.planned_start_date
                    ).days

                # Planned end date crossed
                elif (
                        task.planned_end_date
                        and today > task.planned_end_date
                ):
                    delay = (
                            today - task.planned_end_date
                    ).days

            task.delay_days = delay

    @api.depends('parent_id')
    def _compute_allowed_subtask_stage_ids(self):
        is_manager = self.env.user.has_group('project.group_project_manager')
        for task in self:
            if not task.parent_id:
                task.allowed_subtask_stage_ids = False
                continue
            stages = self.env['project.subtask.stage'].search([])
            if not is_manager:
                stages = stages.filtered(lambda s: not s.is_submit_stage and s.allowed_for_employee)
            else:
                stages = stages.filtered('allowed_for_employee')
            task.allowed_subtask_stage_ids = stages

    @api.constrains('subtask_stage_id', 'parent_id')
    def _check_subtask_stage_consistency(self):
        for task in self:
            if task.subtask_stage_id and not task.parent_id:
                raise ValidationError(_("Subtask stage can only be set on a subtask."))

    def action_submit_for_completion(self):
        self.ensure_one()
        if not self.parent_id:
            raise UserError(_("Only subtasks can be submitted for completion."))
        if self.subtask_stage_id.name != 'In Progress':
            raise UserError(_(
                "Only subtasks in 'In Progress' stage can be submitted "
                "for completion."
            ))
        if self.subtask_stage_id.name == 'Submit for Completion':
            raise UserError(_("This subtask is already waiting for approval."))
        if self.subtask_stage_id.name == 'Completed':
            raise UserError(_("This subtask is already completed."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'subtask.submit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_id': self.id}
        }

    def action_approve_completion(self):
        self.ensure_one()
        if not self.env.user.has_group('project.group_project_manager'):
            raise AccessError(_("Only managers can approve completion."))
        if self.subtask_stage_id.name != 'Submit for Completion':
            raise UserError(_("This subtask is not in 'Submit for Completion' stage."))
        completed_stage = self.env['project.subtask.stage'].search(
            [('name', '=', 'Completed')], limit=1
        )
        if not completed_stage:
            raise UserError(_("Completed stage not found."))

        # Mark subtask as complete and stamp actual end date
        super(ProjectTask, self).write({
            'subtask_stage_id': completed_stage.id,
            'state': '1_done',
            'actual_end_date': fields.Date.today(),
        })

        employee = self.submitted_by  # res.users
        employee_partner = employee.partner_id

        self.message_post(
            body=Markup("""
                <b>Subtask Approved</b><br/>
                Approved By: %s<br/><br/>
                @%s Your submission has been approved.
            """) % (
                self.env.user.name,
                employee.name,
            ),
            partner_ids=[employee_partner.id],  # notify employee,
            subtype_xmlid='mail.mt_comment',
            message_type='notification',

        )

        # Sync parent state & actual dates up the hierarchy chain
        self._sync_parent_state()
        self._sync_project_status()
        return True

    def action_reject_completion(self):
        self.ensure_one()
        if not self.env.user.has_group('project.group_project_manager'):
            raise AccessError(_("Only managers can reject completion."))
        if self.subtask_stage_id.name != 'Submit for Completion':
            raise UserError(_("Only submitted subtasks can be rejected."))

        # Sync parent state (will handle parent actual end date removal dynamically)
        # self._sync_parent_state()
        # self._sync_project_status()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Subtask'),
            'res_model': 'subtask.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
            }
        }

    def _update_parent_dates(self):
        """
        Recursively update parent task's planned start/end dates based on ALL children.
        Then propagate upward until there is no more parent.
        Finally update the project dates.
        """
        for task in self:
            if not task.parent_id:
                continue

            parent = task.parent_id

            all_children = self.env['project.task'].search([
                ('id', 'child_of', parent.id),
                ('id', '!=', parent.id),
            ])

            child_starts = all_children.filtered('planned_start_date').mapped('planned_start_date')
            child_ends = all_children.filtered('planned_end_date').mapped('planned_end_date')

            vals = {}
            if child_starts:
                vals['planned_start_date'] = min(child_starts)
            if child_ends:
                vals['planned_end_date'] = max(child_ends)

            if vals:
                super(ProjectTask, parent).write(vals)

            if parent.parent_id:
                parent._update_parent_dates()

        self._update_project_dates()

    def _update_project_dates(self):
        """
        Update the project's Planned Date based on earliest start
        and latest end across all top-level tasks.
        """
        projects = self.mapped('project_id').filtered(lambda p: p.id)
        for project in projects:
            top_tasks = self.env['project.task'].search([
                ('project_id', '=', project.id),
                ('parent_id', '=', False),
            ])

            start_dates = top_tasks.filtered('planned_start_date').mapped('planned_start_date')
            end_dates = top_tasks.filtered('planned_end_date').mapped('planned_end_date')

            vals = {}
            if start_dates:
                vals['date_start'] = min(start_dates)
            if end_dates:
                vals['date'] = max(end_dates)

            if vals:
                project.write(vals)

    def _sync_parent_state(self):
        """
        Sync parent task state, actual start date, and actual end date based on its subtasks:
        - Parent actual_start_date = min(subtask actual_start_dates) if any subtask has started
        - If ALL subtasks are '1_done' → parent state = '1_done', parent actual_end_date = max(subtask actual_end_dates)
        - If ANY subtask is '01_in_progress' → parent state = '01_in_progress', parent actual_end_date = False
        Then recurse up the hierarchy.
        """
        for task in self:
            if not task.parent_id:
                continue

            parent = task.parent_id
            all_subtasks = self.env['project.task'].search([
                ('parent_id', '=', parent.id),
            ])

            if not all_subtasks:
                continue

            all_done = all(st.state == '1_done' for st in all_subtasks)
            any_in_progress = any(st.state == '01_in_progress' for st in all_subtasks)

            parent_vals = {}

            # ----- Handle Actual Start Date Propagation -----
            start_dates = all_subtasks.filtered('actual_start_date').mapped('actual_start_date')
            if start_dates:
                earliest_start = min(start_dates)
                if parent.actual_start_date != earliest_start:
                    parent_vals['actual_start_date'] = earliest_start

            # ----- Handle State & Actual End Date Propagation -----
            if all_done:
                parent_vals['state'] = '1_done'
                end_dates = all_subtasks.filtered('actual_end_date').mapped('actual_end_date')
                parent_vals['actual_end_date'] = max(end_dates) if end_dates else fields.Date.today()
            elif any_in_progress:
                parent_vals['state'] = '01_in_progress'
                parent_vals['actual_end_date'] = False  # Incomplete if any subtask is reopened

            # Write properties back inside a single execution payload
            if parent_vals:
                super(ProjectTask, parent).write(parent_vals)

            # Recurse up if parent also has a parent
            if parent.parent_id:
                parent._sync_parent_state()

    def _sync_project_status(self):
        """
        Sync the project's last_update_status based on task states:
        - If ALL top-level tasks are '1_done' → project status = 'done'
        - Otherwise → project status = 'on_track'
        """
        projects = self.mapped('project_id').filtered(lambda p: p.id)
        for project in projects:
            top_tasks = self.env['project.task'].search([
                ('project_id', '=', project.id),
                ('parent_id', '=', False),
            ])

            if not top_tasks:
                continue

            all_done = all(t.state == '1_done' for t in top_tasks)

            if all_done:
                project.write({'last_update_status': 'done'})
            else:
                project.write({'last_update_status': 'on_track'})

    def _sync_parent_assignees(self):
        """
        Sync parent task assignees with subtasks.
        - New subtask inherits parent's assignees
        - Existing subtasks update when parent assignee changes
        """
        for task in self:
            if task.parent_id:
                task.user_ids = [(6, 0, task.parent_id.user_ids.ids)]

    def _sync_parent_assignees_from_subtasks(self):
        for task in self.filtered('parent_id'):
            parent = task.parent_id

            all_users = parent.child_ids.mapped('user_ids')

            parent.write({
                'user_ids': [(6, 0, all_users.ids)]
            })

    def _check_consultant_access(self):
        """
        Prevent consultants from editing tasks not assigned to them.
        Allow access if:
        - The task is directly assigned to them, OR
        - The task is a parent task that has subtasks assigned to them
        """
        if self.env.user.has_group(
                'project_mainstaypeopleconsulting.group_project_consultant'
        ):
            for task in self:
                directly_assigned = self.env.user in task.user_ids
                has_assigned_subtask = self.env.user in task.child_ids.mapped('user_ids')

                if not directly_assigned and not has_assigned_subtask:
                    raise AccessError(_(
                        "As a Project Consultant, you can only edit tasks "
                        "assigned to you. Task '%s' is not assigned to you."
                    ) % task.name)

    @api.model
    def _default_subtask_stage(self):
        parent_id = self.env.context.get('default_parent_id')
        if parent_id:
            stage = self.env['project.subtask.stage'].search(
                [('name', '=', 'Yet to Start')],
                limit=1
            )
            return stage.id
        return False

    @api.model_create_multi
    def create(self, vals_list):

        yet_to_start = self.env['project.subtask.stage'].search(
            [('name', '=', 'Yet to Start')],
            limit=1
        )
        for vals in vals_list:
            # only for subtasks
            if vals.get('parent_id') and not vals.get('subtask_stage_id'):
                vals['subtask_stage_id'] = yet_to_start.id
            if self.env.user.has_group(
                    'project_mainstaypeopleconsulting.group_project_consultant'
            ):
                raise AccessError(_("Project Consultants are not allowed to create tasks."))

        tasks = super().create(vals_list)

        subtasks = tasks.filtered('parent_id')
        if subtasks:
            subtasks._sync_parent_assignees()
            subtasks._sync_parent_assignees_from_subtasks()
            for subtask in subtasks:
                subtask._update_parent_dates()
            subtasks._sync_parent_state()
            subtasks._sync_project_status()
        else:
            tasks._update_project_dates()
            tasks._sync_project_status()

        return tasks

    def write(self, vals):
        self._check_consultant_access()

        if 'subtask_stage_id' in vals:
            new_stage = self.env['project.subtask.stage'].browse(vals['subtask_stage_id'])
            is_manager = self.env.user.has_group('project.group_project_manager')
            for task in self:
                if task.parent_id and not is_manager and new_stage.name == 'Completed':
                    raise UserError(_(
                        "Employees cannot directly mark a subtask as Completed. "
                        "Please use 'Submit for Completion'."
                    ))

            # Map custom subtask stage → Odoo 19 state
            if 'state' not in vals:
                if new_stage.name == 'Completed':
                    vals['state'] = '1_done'

                elif new_stage.name == 'In Progress':
                    vals['state'] = '01_in_progress'

                elif new_stage.name == 'Yet to Start':
                    pass  # keep current state

                elif new_stage.name == 'Submit for Completion':
                    vals['state'] = '01_in_progress'

            # Auto-set actual start date when stage → In Progress
            if new_stage.name == 'In Progress':
                for task in self:
                    if not task.actual_start_date:
                        vals['actual_start_date'] = fields.Date.today()

            # Auto-set actual end date when stage → Completed
            if new_stage.name == 'Completed':
                vals['actual_end_date'] = fields.Date.today()

            # Clear actual end date if moved back from Completed
            if new_stage.name != 'Completed':
                vals['actual_end_date'] = False

        # Also sync state when Odoo's built-in stage_id changes
        if 'stage_id' in vals and 'state' not in vals:
            new_odoo_stage = self.env['project.task.type'].browse(vals['stage_id'])
            stage_name_lower = new_odoo_stage.name.lower()
            if any(word in stage_name_lower for word in ['done', 'complet']):
                vals['state'] = '1_done'
            elif any(word in stage_name_lower for word in ['cancel']):
                vals['state'] = '1_canceled'

        res = super().write(vals)

        # Parent -> Child
        if (
                'user_ids' in vals
                and not self.env.context.get('skip_assignee_sync')
        ):

            parent_tasks = self.filtered(
                lambda t: not t.parent_id
            )

            for parent in parent_tasks:

                children = parent.child_ids.filtered(
                    lambda c:
                    set(c.user_ids.ids)
                    != set(parent.user_ids.ids)
                )

                if children:
                    children.with_context(
                        skip_assignee_sync=True
                    ).write({
                        'user_ids': [(6, 0, parent.user_ids.ids)]
                    })

        # Child -> Parent
        if (
                'user_ids' in vals
                and not self.env.context.get('skip_assignee_sync')
        ):
            self.filtered(
                'parent_id'
            )._sync_parent_assignees_from_subtasks()

        # Parent changed
        if 'parent_id' in vals:
            self.filtered(
                'parent_id'
            )._sync_parent_assignees()

        # Existing logic
        if 'state' in vals or 'subtask_stage_id' in vals:
            self._sync_parent_state()
            self._sync_project_status()

        # If start/end dates changed, trigger the full update chain
        if any(f in vals for f in ['planned_start_date', 'planned_end_date']):
            subtasks = self.filtered('parent_id')
            top_tasks = self.filtered(lambda t: not t.parent_id)

            if subtasks:
                for subtask in subtasks:
                    subtask._update_parent_dates()

            if top_tasks:
                top_tasks._update_project_dates()

        return res

    def fix_existing_subtask_states(self):
        """One-time fix to sync existing subtask stages to Odoo state."""
        completed_stage = self.env['project.subtask.stage'].search(
            [('name', '=', 'Completed')], limit=1
        )
        if completed_stage:
            tasks_to_fix = self.env['project.task'].search([
                ('subtask_stage_id', '=', completed_stage.id),
                ('state', '!=', '1_done'),
            ])
            if tasks_to_fix:
                super(ProjectTask, tasks_to_fix).write({'state': '1_done'})

        in_progress_tasks = self.env['project.task'].search([
            ('subtask_stage_id', '!=', False),
            ('subtask_stage_id.name', '!=', 'Completed'),
            ('state', '=', '1_done'),
        ])
        if in_progress_tasks:
            super(ProjectTask, in_progress_tasks).write({'state': '01_in_progress'})

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """
        For Project Consultants, always restrict search results
        to tasks assigned to them at the ORM level.
        """
        if self.env.user.has_group(
                'project_mainstaypeopleconsulting.group_project_consultant'
        ):
            domain = list(domain) + [('user_ids', 'in', [self.env.uid])]
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)