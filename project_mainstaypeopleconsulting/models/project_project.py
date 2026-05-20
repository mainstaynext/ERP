from odoo import models, fields, api


class Project(models.Model):
    _inherit = 'project.project'

    @api.depends('task_ids.planned_start_date', 'task_ids.planned_end_date')
    def _compute_date_start_end(self):
        for project in self:
            tasks = project.task_ids.filtered(
                lambda t: not t.parent_id  # only top-level tasks
            )
            start_dates = tasks.filtered('planned_start_date').mapped('planned_start_date')
            end_dates = tasks.filtered('planned_end_date').mapped('planned_end_date')
            project.date_start = min(start_dates) if start_dates else False
            project.date = max(end_dates) if end_dates else False