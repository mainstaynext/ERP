from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
from markupsafe import Markup


class SubtaskRejectWizard(models.TransientModel):
    _name = 'subtask.reject.wizard'
    _description = 'Reject Subtask Completion'

    task_id = fields.Many2one(
        'project.task',
        required=True
    )

    rejection_reason = fields.Text(
        string='Reason for Rejection',
        required=True
    )

    def action_confirm_reject(self):
        self.ensure_one()

        task = self.task_id

        if not self.env.user.has_group('project.group_project_manager'):
            raise AccessError(_("Only managers can reject completion."))

        if task.subtask_stage_id.name != 'Submit for Completion':
            raise UserError(_("Only submitted subtasks can be rejected."))

        in_progress_stage = self.env['project.subtask.stage'].search(
            [('name', '=', 'In Progress')],
            limit=1
        )

        if not in_progress_stage:
            raise UserError(_("In Progress stage not found."))

        # Reset task
        super(type(task), task).write({
            'subtask_stage_id': in_progress_stage.id,
            'state': '01_in_progress',
            'actual_end_date': False,
        })

        employee = task.submitted_by
        employee_partner = employee.partner_id

        task.message_post(
            body=Markup("""
                <b>Subtask Rejected</b><br/>
                Rejected By: %s<br/><br/>
                <b>Reason:</b><br/>
                %s<br/><br/>
                @%s Your submission was rejected.
                Please update work and resubmit.
            """) % (
                self.env.user.name,
                self.rejection_reason,
                employee.name,
            ),
            partner_ids=[employee_partner.id],
            subtype_xmlid='mail.mt_comment',
            message_type='notification',
        )

        task._sync_parent_state()
        task._sync_project_status()

        return {'type': 'ir.actions.act_window_close'}


class SubtaskSubmitWizard(models.TransientModel):
    _name = 'subtask.submit.wizard'
    _description = 'Submit Subtask for Completion'

    task_id = fields.Many2one(
        'project.task',
        string='Subtask',
        required=True
    )

    comment = fields.Text(
        'Comments',
        required=True
    )

    supporting_link = fields.Char(
        'Supporting Document (SharePoint Link)',
        required=True
    )

    @api.constrains('supporting_link')
    def _check_supporting_link(self):
        for rec in self:
            if rec.supporting_link and not rec.supporting_link.startswith(('http://', 'https://')):
                raise ValidationError(
                    _("Please enter a valid URL starting with http:// or https://")
                )

    def action_submit(self):
        self.ensure_one()

        task = self.task_id

        submit_stage = self.env['project.subtask.stage'].search(
            [('name', '=', 'Submit for Completion')],
            limit=1
        )

        if not submit_stage:
            raise ValidationError(
                _("'Submit for Completion' stage not found.")
            )

        task.write({
            'subtask_stage_id': submit_stage.id,
            'submission_comment': self.comment,
            'submission_document_link': self.supporting_link,
            'submitted_by': self.env.user.id,
            'submitted_on': fields.Datetime.now(),
        })

        # Notify in chatter
        project_manager = task.project_id.user_id

        if not project_manager:
            raise ValidationError(_("No Project Manager assigned."))

        manager_partners = project_manager.partner_id
        manager_names = project_manager.name

        task.message_post(
            body=Markup("""
                <b>Subtask Submitted for Completion</b><br/>
                Employee: %s<br/>
                Comment: %s<br/>
                Document:
                <a href="%s" target="_blank">Open Link</a><br/>
                Waiting for approval from: %s<br/><br/>
                @%s Please review and approve.
            """) % (
                self.env.user.name,
                self.comment,
                self.supporting_link,
                manager_names or "Manager",
                manager_names
            ),
            partner_ids=manager_partners.ids,
            subtype_xmlid='mail.mt_comment',
            message_type='notification',
        )

        return {'type': 'ir.actions.act_window_close'}