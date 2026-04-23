<<<<<<< HEAD
from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cliente_id = fields.Many2one(
        'res.partner',
        string="Cliente",
        tracking=True,
        help="Este campo es utilizado para diferir un producto para un cliente en especifico."
=======
from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cliente_id = fields.Many2one(
        'res.partner',
        string="Cliente",
        tracking=True,
        help="Este campo es utilizado para diferir un producto para un cliente en especifico."
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    )