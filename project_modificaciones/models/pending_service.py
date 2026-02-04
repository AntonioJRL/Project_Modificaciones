from odoo import models, fields, api, _
from datetime import datetime
from markupsafe import Markup
from odoo.exceptions import ValidationError


import logging
_logger = logging.getLogger(__name__)


class PendingService(models.Model):
    _name = 'pending.service'
    _description = 'Servicio Pendiente'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Nombre",
        required=True, copy=False, readonly=True,
        index='trigram',
        default=lambda self: _('New'))
    order_number = fields.Char(string='Número de Orden', tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('assigned', 'Asignada'),
        ('canceled', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)
    supervisor_id = fields.Many2one(
        'hr.employee', string='Supervisor', tracking=True)
    disciplina_id = fields.Many2one(
        'license.disciplina', string='Disciplina', required=True, tracking=True)
    service_line_ids = fields.One2many(
        'pending.service.line', 'service_id', string='Líneas de Servicio', delete='cascade')
    total = fields.Float(string='Total', compute='_compute_total', store=True)
    date = fields.Date(string='Fecha', default=datetime.today(), tracking=True)
    license_ids = fields.Many2many(
        'license.license', string='Licencias', tracking=True)

    ot_number = fields.Char(string='OT', tracking=True)
    planta = fields.Char(string='Planta', tracking=True)
    supervisor_planta_id = fields.Many2one(
        'supervisor.area', string='Supervisor de Planta', tracking=True)
    manage_via_or = fields.Boolean(
        string='Gestionar mediante OR', default=False, tracking=True)
    descripcion_servicio = fields.Text(
        string='Descripción del Servicio', tracking=True)  # Nuevo campo
    active = fields.Boolean(string='Activo', default=True,
                            tracking=True)  # Para archivar

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if 'disciplina_id' in vals:
                    disciplina = self.env['license.disciplina'].browse(
                        vals['disciplina_id'])
                    sequence = disciplina.sequence_id
                    if sequence:
                        vals['name'] = sequence.next_by_id()
                    else:
                        vals['name'] = _('New')
                else:
                    vals['name'] = _('New')
        return super(PendingService, self).create(vals_list)

    @api.depends('service_line_ids.total')
    def _compute_total(self):
        for service in self:
            service.total = sum(service.service_line_ids.mapped('total'))

    def action_set_to_pending(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'pending'
            else:
                raise ValidationError(
                    _("El servicio debe estar en estado 'Borrador' para pasar a 'Pendiente'."))

    def action_assign(self):
        self.write({'state': 'assigned'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_set_to_draft(self):
        self.write({'state': 'draft'})

    def toggle_active(self):
        for record in self:
            record.active = not record.active

    def unlink(self):
        # Eliminar las líneas de servicio asociadas antes de eliminar el servicio pendiente
        self.service_line_ids.unlink()
        return super(PendingService, self).unlink()

    # Control de Obra
    cliente_servicio = fields.Many2one(
        'res.partner', string="Cliente", help="Cliente al que se realizara el servicio.", tracking=True)

    # centro_trabajo = fields.Many2one('control.centro.trabajo', string="Centro Trabajo", help="Centro De Trabajo Donde Se Esta Realizando El Servicio", tracking=True)

    planta_centro = fields.Many2one(
        'control.planta', string="Planta", help="Planta donde se realizara el servicio.", tracking=True)

    task_count = fields.Integer(
        string='Cantidad de Tareas', compute='_compute_task_count')

    sale_order_count = fields.Integer(
        string='Órdenes de Venta', compute='_compute_sale_order_count')

    scaffolding_count = fields.Integer(
        string='Andamios', compute='_compute_scaffolding_count')

    @api.depends('sale_order_count')
    def _compute_scaffolding_count(self):
        for record in self:
            # Buscar andamios relacionados a las órdenes de venta de este servicio
            sale_orders = self.env['sale.order'].search([
                ('pending_service_id', '=', record.id)
            ])
            if sale_orders and 'scaffolding.installation' in self.env:
                record.scaffolding_count = self.env['scaffolding.installation'].search_count([
                    ('sale_order_id', 'in', sale_orders.ids)
                ])
            else:
                record.scaffolding_count = 0

    def action_view_scaffoldings(self):
        self.ensure_one()
        if 'scaffolding.installation' not in self.env:
            return

        sale_orders = self.env['sale.order'].search([
            ('pending_service_id', '=', self.id)
        ])

        domain = [('sale_order_id', 'in', sale_orders.ids)]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Andamios Relacionados'),
            'res_model': 'scaffolding.installation',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'default_sale_order_id': sale_orders[0].id if sale_orders else False},
        }

    def _compute_task_count(self):
        for record in self:
            # Buscamos tareas que en su nombre contengan el nombre de este servicio
            # O mejor aún, podrías añadir un campo Many2one en project.task que apunte aquí
            record.task_count = self.env['project.task'].search_count([
                ('project_id', '=', record.supervisor_id.proyecto_supervisor.id),
                ('name', 'ilike', record.name)
            ])

    @api.depends()
    def _compute_sale_order_count(self):
        for record in self:
            record.sale_order_count = self.env['sale.order'].search_count([
                ('pending_service_id', '=', record.id)
            ])

    def action_create_project_update(self):
        """
        Generar o actualizar un reporte de 'Project Update' (Avance Físico)
        con las líneas de este servicio pendiente.
        """
        self.ensure_one()

        if not self.supervisor_id.proyecto_supervisor:
            raise ValidationError(
                _("El supervisor no tiene un proyecto asignado."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Registrar Avance'),
            'res_model': 'pending.service.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_service_id': self.id,
                'default_date': self.date or fields.Date.context_today(self),
                'active_id': self.id,
            }
        }

    def action_create_tasks(self):
        for record in self:
            # 1. VALIDACIÓN PREVIA
            if not record.supervisor_id or not record.supervisor_id.proyecto_supervisor:
                raise ValidationError(
                    _("El supervisor no tiene un proyecto asignado en su ficha de empleado."))

            project = record.supervisor_id.proyecto_supervisor
            created_tasks = self.env['project.task']

            # 2. PROCESO DE CREACIÓN
            for line in record.service_line_ids:
                # Si ya tiene tarea, saltar
                if line.task_id:
                    continue

                user_id = record.supervisor_id.user_id.id if record.supervisor_id.user_id else False

                # Crear la tarea
                task = self.env['project.task'].create({
                    'name': f"P{line.partida:02d} {record.name} - {line.product_id.display_name}",
                    'project_id': project.id,
                    'description': record.descripcion_servicio or '',
                    'user_ids': [(4, user_id)] if user_id else False,
                    'planta_trabajo': record.planta_centro.id,
                    'piezas_pendientes': line.quantity,
                    'supervisor_interno': record.supervisor_id.id,
                    'supervisor_cliente': record.supervisor_planta_id.id,
                    'partner_id': record.cliente_servicio.id,
                    'producto_relacionado': line.product_id.id,
                })

                # Link task to line persistently
                line.task_id = task.id
                created_tasks |= task

            # 3. NOTIFICACIÓN UI (Sin historial en chatter)
            if created_tasks:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Tareas Creadas'),
                        'message': _('Se han generado %s tareas correctamente en el proyecto %s.') % (len(created_tasks), project.name),
                        'type': 'success',
                        'sticky': False,
                        'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                    }
                }
        return True

    # Acción para el Smart Button
    def action_view_tasks(self):
        self.ensure_one()
        tasks = self.env['project.task'].search(
            [('project_id', '=', self.supervisor_id.proyecto_supervisor.id), ('name', 'ilike', self.name)])
        if len(tasks) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Tarea del Servicio'),
                'res_model': 'project.task',
                'res_id': tasks.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tareas del Servicio'),
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.supervisor_id.proyecto_supervisor.id), ('name', 'ilike', self.name)],
            'context': {'default_project_id': self.supervisor_id.proyecto_supervisor.id},
        }

    # Acción para el Smart Button del proyecto
    def action_view_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Proyecto'),
            'res_model': 'project.project',
            'res_id': self.supervisor_id.proyecto_supervisor.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Acción para el Smart Button de órdenes de venta
    def action_view_sale_orders(self):
        self.ensure_one()
        sale_orders = self.env['sale.order'].search(
            [('pending_service_id', '=', self.id)])
        if len(sale_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Orden de Venta'),
                'res_model': 'sale.order',
                'res_id': sale_orders.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Órdenes de Venta'),
                'res_model': 'sale.order',
                'view_mode': 'tree,form',
                'domain': [('pending_service_id', '=', self.id)],
                'context': {'default_pending_service_id': self.id},
            }

    def action_create_sale_order(self):
        for record in self:
            if not record.cliente_servicio:
                raise ValidationError(
                    _("Debe seleccionar un Cliente para generar la Orden de Venta."))

            if not record.supervisor_id.proyecto_supervisor:
                raise ValidationError(
                    _("El supervisor no tiene un proyecto asignado."))

            # 1. Crear la Orden de Venta (Cabecera)
            sale_order_vals = {
                'partner_id': record.cliente_servicio.id,
                'analytic_account_id': record.supervisor_id.proyecto_supervisor.analytic_account_id.id,
                'origin': record.name,
                # Forzamos el proyecto en la orden si tienes campos personalizados
                'project_id': record.supervisor_id.proyecto_supervisor.id,
            }
            # Solo asignar pending_service_id si hay tareas creadas
            if record.task_count > 0:
                sale_order_vals['pending_service_id'] = record.id

            sale_order = self.env['sale.order'].create(sale_order_vals)

            # 2. Crear las líneas de la Orden de Venta
            for line in record.service_line_ids:
                sol = self.env['sale.order.line'].create({
                    'order_id': sale_order.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    # 'price_unit': line.price_unit,
                    # Fix: Use pricelist price
                    'price_unit': sale_order.pricelist_id._get_product_price(line.product_id, line.quantity) if sale_order.pricelist_id else line.price_unit,
                    'name': f"P{line.partida:02d} {line.product_id.get_product_multiline_description_sale()}",
                    'pending_line_id': line.id,
                })

                # Las tareas existentes se asignarán automáticamente al confirmar la orden

            # 4. Mensaje de éxito con Markup
            msg = Markup(_(
                "<div style='background-color: #e9f7ef; border: 1px solid #28a745; padding: 10px;'>"
                "   <p><b>✅ Orden de Venta %s generada</b></p>"
                "   <p>Se han creado las tareas vinculadas en el proyecto del supervisor.</p>"
                "</div>"
            )) % sale_order.name
            record.message_post(body=msg)

            record.write({'state': 'assigned'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Actualizar valores del campos total_avances
    def action_update_progress(self):
        """
        Recalcula total_avances.
        1. Busca los avances (project.sub.update) de la tarea asignada.
        2. Vincula esos avances a la línea para futuros cálculos.
        3. Suma el progreso.
        """
        messages = []
        for record in self:
            for line in record.service_line_ids:
                if line.task_id:
                    # Buscamos todos los avances que pertenezcan a esa tarea
                    avances = self.env['project.sub.update'].search([
                        ('task_id', '=', line.task_id.id)
                    ])

                    if avances:
                        # Vinculamos y re-calculamos
                        avances.write({'pending_service_line_id': line.id})
                        total_calculado = sum(avances.mapped('unit_progress'))
                        messages.append(_("Línea %s: OK. Total: %s (De %s registros)") % (
                            line.partida, total_calculado, len(avances)))
                    else:
                        messages.append(_("Línea %s: Tarea %s sin avances registrados.") % (
                            line.partida, line.task_id.name))
                else:
                    messages.append(
                        _("Línea %s: No tiene tarea asignada.") % line.partida)

        # Force recompute of stored field
        self.service_line_ids._compute_total_avances()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recálculo Completado'),
                'message': "\n".join(messages),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    avances_pend = fields.One2many(
        'project.sub.update',
        'pending_service_id',
        string="Avances Relacionado"
    )


class PendingServiceLine(models.Model):
    _name = 'pending.service.line'
    _description = 'Línea de Servicio Pendiente'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Secuencia', default=10)
    partida = fields.Integer(
        string='Partida', compute='_compute_partida', store=True)

    @api.depends('sequence', 'service_id.service_line_ids')
    def _compute_partida(self):
        for service in self.mapped('service_id'):
            # Sort by sequence only to avoid NewId comparison error
            # Python sort is stable, so original insertion order is preserved for ties
            lines = service.service_line_ids.sorted(key=lambda l: l.sequence)
            for i, line in enumerate(lines, 1):
                old_partida = line.partida
                line.partida = i

                # If part of a reorder (not new creation) and has task, rename it
                if old_partida != i and line.task_id:
                    # Reconstruct name: P{02d} ServiceName - ProductDisplayName
                    new_name = f"P{i:02d} {line.service_id.name} - {line.product_id.display_name}"
                    # Only write if different to avoid excess writes
                    if line.task_id.name != new_name:
                        line.task_id.name = new_name

    service_id = fields.Many2one(
        'pending.service', string='Servicio Pendiente', required=True)
    product_id = fields.Many2one(
        'product.product', string='Producto', required=True)
    quantity = fields.Float(string='Cantidad', required=True)
    price_unit = fields.Float(
        string='Precio Unitario', compute='_compute_price_unit', inverse='_inverse_price_unit', store=True)
    total = fields.Float(string='Total', compute='_compute_total', store=True)

    # Campo para la tarea asociada (se setea cuando se crea la tarea)
    task_id = fields.Many2one(
        'project.task', string='Tarea Asociada', copy=False)

    # Total de avances físicos asociados a la tarea
    sub_update_ids = fields.One2many(
        'project.sub.update', 'pending_service_line_id', string='Avances Físicos')

    total_avances = fields.Float(
        string='Total Avances', compute='_compute_total_avances', store=True)

    @api.depends('sub_update_ids.unit_progress', 'sub_update_ids.avances_state')
    def _compute_total_avances(self):
        for line in self:
            # Sumamos solo los avances que no estén en borrador (opcional, según lógica de negocio)
            # Si se desea sumar todo, quitar el filtro de state.
            avances = line.sub_update_ids
            line.total_avances = sum(avances.mapped('unit_progress'))

    @api.depends('product_id')
    def _compute_price_unit(self):
        for line in self:
            if line.product_id:
                # Use lst_price to get the variant's specific price (including extra charges)
                line.price_unit = line.product_id.lst_price
            else:
                line.price_unit = 0.0

    def _inverse_price_unit(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.price_unit

    def action_open_task(self):
        self.ensure_one()
        if self.task_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'project.task',
                'res_id': self.task_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    @api.depends('quantity', 'price_unit')
    def _compute_total(self):
        for line in self:
            line.total = line.quantity * line.price_unit
