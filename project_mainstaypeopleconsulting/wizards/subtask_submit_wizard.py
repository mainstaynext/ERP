from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SubtaskSubmitWizard(models.TransientModel):
    _name = 'subtask.submit.wizard'
    _description = 'Submit Subtask for Completion'

    task_id = fields.Many2one('project.task', string='Subtask', required=True)
    comment = fields.Text('Comments', required=True)
    supporting_link = fields.Char('Supporting Document (SharePoint Link)', required=True)

    @api.constrains('supporting_link')
    def _check_supporting_link(self):
        for rec in self:
            if rec.supporting_link and not rec.supporting_link.startswith(('http://', 'https://')):
                raise ValidationError(_("Please enter a valid URL starting with http:// or https://"))

    def action_submit(self):
        self.ensure_one()
        task = self.task_id
        submit_stage = self.env['project.subtask.stage'].search([('name', '=', 'Submit for Completion')], limit=1)
        if not submit_stage:
            raise ValidationError(_("'Submit for Completion' stage not found."))
        task.write({
            'subtask_stage_id': submit_stage.id,
            'submission_comment': self.comment,
            'submission_document_link': self.supporting_link,
            'submitted_by': self.env.user.id,
            'submitted_on': fields.Datetime.now(),
        })
        return {'type': 'ir.actions.act_window_close'}