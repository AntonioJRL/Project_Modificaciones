# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Campo añadido para satisfacer validación de vista externa/heredada
    login_date_sort = fields.Datetime(
        string='Login Date Sort',
        related='login_date',
        store=True,
        readonly=True
    )
