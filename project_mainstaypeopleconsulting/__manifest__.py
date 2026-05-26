{
    'name': 'Subtask Enhancement',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Separate stages, submit for approval workflow',
    'description': """
        Custom subtask stages with employee submission and manager approval.
    """,
    'author': 'Shivang',
    'depends': ['project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/subtask_stage_data.xml',
        'views/project_subtask_stage_views.xml',
        'views/project_task_views.xml',
        'views/subtask_submit_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}