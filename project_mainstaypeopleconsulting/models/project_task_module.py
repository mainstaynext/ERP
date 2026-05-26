from odoo import models, fields


class ProjectTaskModule(models.Model):
    _name = 'project.task.module'
    _description = 'Project Task Module'
    _order = 'sequence, name'

    name = fields.Char(string='Module Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Module name must be unique.'),
    ]