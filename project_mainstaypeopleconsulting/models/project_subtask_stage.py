from odoo import models, fields

class ProjectSubtaskStage(models.Model):
    _name = 'project.subtask.stage'
    _description = 'Subtask Stage'
    _order = 'sequence, id'

    name = fields.Char('Stage Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    is_closed = fields.Boolean('Closed Stage', help='Subtask in this stage is considered closed.')
    is_submit_stage = fields.Boolean('Submit for Completion Stage', help='Stage where employee requests approval.')
    allowed_for_employee = fields.Boolean('Visible to Employees', default=True,
        help='If unchecked, only managers can see/use this stage.')