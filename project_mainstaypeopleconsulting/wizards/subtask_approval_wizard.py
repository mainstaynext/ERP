from odoo import models, fields, _
from odoo.exceptions import UserError


class SubtaskApprovalWizard(models.TransientModel):
    _name = 'subtask.approval.wizard'
    _description = 'Subtask Approval Wizard'

    task_id = fields.Many2one('project.task', string='Subtask', required=True)
    comment = fields.Text('Approval Comment', required=True)
    supporting_link = fields.Char('Supporting Document (SharePoint Link)')

    def action_confirm_approve(self):
        for wizard in self:
            task = wizard.task_id
            if task.approval_state != 'pending':
                raise UserError(_("This subtask is not waiting for approval."))
            completed_stage = self.env['project.subtask.stage'].search(
                [('name', '=', 'Completed')], limit=1
            )
            if not completed_stage:
                raise UserError(
                    _("'Completed' stage not found. Please check stage configuration.")
                )
            task.write({
                'subtask_stage_id': completed_stage.id,
                'approval_state': 'approved',
                'approval_comment': wizard.comment,
                'supporting_document_link': wizard.supporting_link,
                'approval_date': fields.Datetime.now(),
            })
        return {'type': 'ir.actions.act_window_close'}
