from odoo import fields, models, api, _
from markupsafe import Markup
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
import logging
import json

_logger = logging.getLogger(__name__)


class Task(models.Model):
    _inherit = 'project.task'

    sale_line_id = fields.Many2one(
        "sale.order.line",
        "Sale Order Item",
        copy=False,
        index=True,
        domain="[('is_service', '=', True), ('is_expense', '=', False), ('state', 'in', ['sale', 'done']), ('order_partner_id', '=?', partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    project_id = fields.Many2one(tracking=True)

    state = fields.Selection(
        selection_add=[
            ("01_in_progress", "In Progress"),
            ("1_done", "Done"),
            ("04_waiting_normal", "Waiting"),
        ],
        ondelete={
            "04_waiting_normal": "set default",
            "01_in_progress": "set default",
            "1_done": "set default",
        },
    )

    sale_order_id = fields.Many2one(
        string="Sales Order",
        related="sale_line_id.order_id",
        help="Sales order to which the project is linked.",
    )

    delivered = fields.Float(
        string="Entregado", related="sale_line_id.qty_delivered")
    price_unit = fields.Float(
        string="Precio", related="sale_line_id.price_unit")
    total_pieces = fields.Float(
        string="Unidades (decimal)", related="sale_line_id.product_uom_qty"
    )
    price_subtotal = fields.Float(string="Subtotal", compute="_subtotal")
    qty_invoiced = fields.Float(
        string="Facturado (unidades)", related="sale_line_id.qty_invoiced", store=True
    )
    disc = fields.Many2one(
        string="Especialidad", related="sale_line_id.product_id.categ_id", store=True
    )
    invoiced = fields.Float(
        string="Facturado", compute="_invoiced", store=True)

    # ========== CAMPOS DE ANALYTICS_EXTRA (mod_task.py) ==========
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Moneda",
        store=True,
        readonly=True,
    )
    expense_ids = fields.One2many("hr.expense", "task_id", string="Gastos")
    purchase_ids = fields.One2many(
        "purchase.order", "task_order_id", string="Compras")
    purchase_line_ids = fields.One2many(
        "purchase.order.line", "task_id", string="Líneas de compra"
    )
    requisition_ids = fields.One2many(
        "employee.purchase.requisition", "task_id", string="Requisiciones"
    )

    expense_count = fields.Integer(string="Gastos", compute="_compute_counts")
    purchase_count = fields.Integer(
        string="Compras", compute="_compute_counts")
    requisition_count = fields.Integer(
        string="Requisiciones", compute="_compute_counts")
    stock_move_count = fields.Integer(
        string="Movimientos de Almacén", compute="_compute_counts")

    expense_total_approved = fields.Monetary(
        string="Total gastos (aprobados)",
        compute="_compute_totals",
        currency_field="currency_id",
        store=False,
    )
    purchase_total_approved = fields.Monetary(
        string="Total compras (confirmadas)",
        compute="_compute_totals",
        currency_field="currency_id",
        store=False,
    )
    # ========== FIN CAMPOS DE ANALYTICS_EXTRA ==========

    # ========== CAMPOS DE INTEGRACIÓN ALMACÉN ==========
    stock_move_ids = fields.One2many(
        'stock.move',
        'task_id',
        string='Movimientos de Almacén',
        domain="[('state', '=', 'done'), ('picking_type_id.code', '=', 'outgoing')]"
    )

    stock_move_cost = fields.Monetary(
        string="Costo Mov. Almacén",
        compute='_compute_stock_move_cost',
        currency_field='currency_id'
    )

    @api.depends('stock_move_ids', 'stock_move_ids.state', 'purchase_line_ids', 'purchase_line_ids.state')
    def _compute_stock_move_cost(self):
        for task in self:
            cost = 0.0
            moves = task.stock_move_ids.filtered(lambda m: m.state == 'done')

            moved_qty_per_product = {}
            for move in moves:
                qty = move.quantity
                moved_qty_per_product[move.product_id.id] = moved_qty_per_product.get(
                    move.product_id.id, 0.0) + qty

            purchased_qty_per_product = {}
            purchase_lines = self.env['purchase.order.line'].search([
                ('task_id', '=', task.id),
                ('order_id.state', 'in', ['purchase', 'done'])
            ])
            for line in purchase_lines:
                purchased_qty_per_product[line.product_id.id] = purchased_qty_per_product.get(
                    line.product_id.id, 0.0) + line.product_qty

            for product_id, moved_qty in moved_qty_per_product.items():
                purchased_qty = purchased_qty_per_product.get(product_id, 0.0)
                chargeable_qty = max(0.0, moved_qty - purchased_qty)

                if chargeable_qty > 0:
                    product = task.env['product.product'].browse(product_id)
                    unit_cost = product.standard_price
                    cost += chargeable_qty * unit_cost

            task.stock_move_cost = cost
    # ========== FIN CAMPOS DE INTEGRACIÓN ALMACÉN ==========

    sub_update_ids = fields.One2many(
        "project.sub.update",
        "task_id",
        domain="[('project_id', '=', project_id), ('task_id.id', '=', id)]",
        string="Actualización de tareas",
    )

    sub_update = fields.Many2one(
        "project.sub.update", compute="_last_update", store=False)

    @api.depends("sub_update_ids", "project_id")
    def _last_update(self):
        for u in self:
            if not u.id or isinstance(u.id, models.NewId):
                u.sub_update = False
                continue

            try:
                last_record = u.env["project.sub.update"].sudo().search(
                    [("project_id", "=", u.project_id.id), ("task_id", "=", u.id)],
                    order="id desc",
                    limit=1,
                )
                if last_record and last_record.exists():
                    u.sub_update = last_record.id
                else:
                    u.sub_update = False
            except Exception:
                u.sub_update = False

    last_update = fields.Many2one(
        "project.update", related="sub_update.update_id", string="Última actualización"
    )

    sub_d_update = fields.Many2one(
        "project.sub.update",
        compute="_d_update",
        string="Última actualización de tarea",
        store=False,
    )

    @api.depends("sub_update_ids", "project_id")
    def _d_update(self):
        for u in self:
            if not u.id or isinstance(u.id, models.NewId):
                u.sub_d_update = False
                continue

            try:
                last_record = u.env["project.sub.update"].sudo().search(
                    [("project_id", "=", u.project_id.id), ("task_id", "=", u.id)],
                    order="id desc",
                    limit=1,
                )
                if last_record and last_record.exists():
                    u.sub_d_update = last_record.id
                else:
                    u.sub_d_update = False
            except Exception:
                u.sub_d_update = False

    last_d_update = fields.Many2one(
        "project.update",
        related="sub_d_update.update_id",
        string="Última actualización modificada",
    )

    use_weighted_progress = fields.Boolean(
        string="Progreso ponderado",
        help="Si se activa, el progreso de esta tarea se calculará como la suma ponderada del progreso de sus subtareas.",
        default=False,
    )
    subtask_weight = fields.Float(
        string="Peso en tarea padre (%)",
        help="Porcentaje de impacto que tiene esta subtarea sobre el progreso de la tarea padre. (0-100)",
        default=0.0,
    )
    last_update_date = fields.Datetime(
        related="last_d_update.write_date", string="Modificado por ult. vez"
    )

    quant_progress = fields.Float(
        string="Piezas/Servicio", compute="_units", store=True
    )
    progress = fields.Integer(
        compute="_progress", string="Progreso", store=True)
    progress_percentage = fields.Float(
        compute="_progress_percentage", string="Progreso porcentual", store=True
    )

    is_complete = fields.Boolean(
        string="Complete", compute="_is_complete", default=False, store=True
    )

    centro_trabajo = fields.Many2one(
        "control.centro.trabajo",
        string="Centro Trabajo",
        help="Centro de trabajo en donde se realizara el servicio.",
        tracking=True,
    )

    planta_trabajo = fields.Many2one(
        "control.planta",
        string="Planta",
        help="Planta de trabajo en donde se realizara el servicio.",
        tracking=True,
    )

    supervisor_interno = fields.Many2one(
        "hr.employee",
        string="Supervisor Interno",
        domain="[('supervisa', '=', True)]",
        help="Supervisor Del Trabajo Interno (AYASA)",
        tracking=True,
    )

    supervisor_cliente = fields.Many2one(
        "supervisor.area",
        string="Supervisor Cliente",
        help="Supervisor por parte del cliente al cual se le proporcionara el servicio.",
        tracking=True,
    )

    partida_relacionada = fields.Char(
        string="Partida",
        help="Partida relacionada con la tarea.",
        related="sale_line_id.partida",
        tracking=True,
    )

    tarea_padre = fields.Many2one(
        'project.task',
        related="parent_id",
        string="Tarea Padre",
        help="Muestra la tarea padre si es una subtarea.",
        readonly=True,
    )

    is_control_obra = fields.Boolean(
        string="Tarea Control Obra",
        default=False,
        compute="_compute_is_control_obra",
        help="Indica que esta tarea es un servicio a realizar, relacionada a un proyecto de obra dentro del modulo Control Obra.",
        store=True,
    )

    project_domain_string = fields.Char(
        compute="_compute_project_domain_string",
        readonly=True,
        store=False
    )

    @api.depends('is_control_obra', 'company_id')
    def _compute_project_domain_string(self):
        for task in self:
            domain = [('active', '=', True)]
            if task.company_id:
                domain += ['|', ('company_id', '=', False),
                           ('company_id', '=', task.company_id.id)]
            else:
                domain += ['|', ('company_id', '=', False),
                           ('company_id', '!=', False)]

            if task.is_control_obra:
                domain.append(('is_proyecto_obra', '=', True))

            task.project_domain_string = str(domain)

    # CAMPOS Y METODOS PARA EL FLUJO DE APROBACIÓN
    approval_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("to_approve", "En Aprobación"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazada"),
        ],
        string="Estado de Aprobación",
        default="draft",
        copy=False,
    )

    approver_id = fields.Many2one(
        "res.users",
        string="Aprobador (Superintendente)",
        copy=False,
        tracking=True,
        readonly=True,
    )

    approval_activity_id = fields.Many2one(
        "mail.activity",
        string="Actividad de Aprobación",
        copy=False,
    )

    can_user_approve = fields.Boolean(
        string="Usuario actual puede aprobar",
        compute="_compute_can_user_approve",
    )

    piezas_pendientes = fields.Float(
        string="Piezas Pendientes",
        tracking=True,
    )

    producto_relacionado = fields.Many2one(
        'product.product',
        string="Producto Relacionado A la Tarea",
    )

    # -------------------------------------------------------------------------
    # MÉTODOS
    # -------------------------------------------------------------------------

    @api.depends("sale_line_id.qty_invoiced")
    def _invoiced(self):
        for u in self:
            u.invoiced = u.qty_invoiced * u.price_unit

    def web_read(self, specification):
        """
        DEBUG METHOD: Traps the KeyError 586 to identify the culprit field.
        """
        # Pre-check values in memory before the crash
        for task in self:
            for field, spec in specification.items():
                try:
                    val = task[field]
                    # Check for record (Many2one) with ID 586
                    if hasattr(val, 'id') and val.id == 586:
                        _logger.critical(
                            f" >>>>>> CULPRIT FOUND: Field '{field}' has value 586 on task {task.id} <<<<<<")
                    # Check for raw integer 586
                    elif val == 586:
                        _logger.critical(
                            f" >>>>>> CULPRIT FOUND: Field '{field}' has value 586 on task {task.id} <<<<<<")
                except Exception:
                    pass

        return super().web_read(specification)

    @api.model
    def _check_to_recompute(self):
        return [id]

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress",
        "project_id.update_ids",
        "use_weighted_progress",
        "progress",
        "total_pieces",
        "child_ids.progress",
        "child_ids.subtask_weight",
        "state"
    )
    def _units(self):
        for u in self:
            if not u.id:
                continue

            # CASO 1: Tarea Padre Ponderada (Calcula en base a hijos)
            if u.use_weighted_progress:
                # 1. Aporte Ponderado de Hijos
                weighted_pct = 0.0
                for child in u.child_ids:
                    current_sub_progress = child.progress or 0
                    if current_sub_progress > 0:
                        weighted_pct += (current_sub_progress /
                                         100.0) * child.subtask_weight

                weighted_units = (weighted_pct / 100.0) * u.total_pieces

                # 2. Aporte Directo (Progreso reportado directamente en esta tarea)
                # Usamos los updates vinculados DIRECTAMENTE a esta tarea (u.id)
                direct_units = sum(u.sub_update_ids.mapped("unit_progress"))

                u.quant_progress = weighted_units + direct_units

                # Consistencia: Solo si el padre está Hecho, asumimos 100% global
                if u.state == '1_done':
                    u.quant_progress = u.total_pieces

            # CASO 2: Subtarea / Tarea Normal (Calcula sumando sus avances)
            else:
                # Aquí aplicamos tu lógica original: Suma pura de avances.
                # NO forzamos el total si está 'Done', respetamos lo reportado (25/50).
                progress = (
                    u.env["project.sub.update"]
                    .search([("project_id", "=", u.project_id.id), ("task_id", "=", u.id)])
                    .mapped("unit_progress")
                )
                u.quant_progress = sum(progress)

            # Escribir en la SO (Reflejo en Ventas)
            # Solo escribimos si NO somos una subtarea cuyo padre ya gestiona el progreso global
            should_write_so = True
            # Si soy subtarea y mi padre es ponderado, mi padre escribe su total global, no yo.
            # (Aunque ahora el padre incluye mi aporte, sigue siendo el padre el que representa la linea principal si es el caso)
            if u.parent_id and u.parent_id.use_weighted_progress:
                should_write_so = False

            if u.sale_line_id and should_write_so:
                u.sale_line_id.qty_delivered = u.quant_progress

    @api.depends(
        "sub_update_ids",
        "sub_update_ids.unit_progress",
        "project_id.update_ids",
        "quant_progress",
        "total_pieces",
        "use_weighted_progress",
        "child_ids.progress",
        "child_ids.subtask_weight",
        "child_ids.state",
        "state",
    )
    def _progress(self):
        for u in self:
            progress = 0.0

            if u.use_weighted_progress:
                # Ahora que quant_progress incluye (Hijos Ponderados + Padre Directo),
                # el porcentaje es: quant_progress / TOTAL GLOBAL
                global_total = u.sale_line_id.product_uom_qty if u.sale_line_id else u.total_pieces

                if global_total > 0:
                    progress = (u.quant_progress / global_total) * 100.0
                else:
                    progress = 0.0

            # PRIORIDAD 2: Cálculo Dinámico si es SUBTAREA PONDERADA
            elif u.parent_id and u.parent_id.use_weighted_progress and u.subtask_weight > 0:
                # La meta es calculada: Total Padre * Peso Subtarea
                # Ejemplo: 100 * 50% = 50 unidades meta
                denominator = u.parent_id.total_pieces * \
                    (u.subtask_weight / 100.0)

                # Evitar división por cero
                if denominator > 0:
                    progress = (u.quant_progress / denominator) * 100
                else:
                    progress = 0.0

            # PRIORIDAD 3: Cálculo estándar por piezas (Tareas normales o Padres no ponderados)
            elif u.total_pieces and u.total_pieces > 0:
                progress = (u.quant_progress / u.total_pieces) * 100

            u.progress = min(100, int(round(progress)))
            u.progress_percentage = u.progress / 100.0

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "project_id.update_ids"
    )
    def _progress_percentage(self):
        for u in self:
            if not u.id:
                continue
            u.progress_percentage = u.progress / 100

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "project_id.update_ids"
    )
    def _subtotal(self):
        for u in self:
            if not u.id:
                continue
            subtotal = (
                u.env["sale.order.line"]
                .search([("id", "=", u.sale_line_id.id)])
                .mapped("price_subtotal")
            )
            if subtotal:
                u.price_subtotal = float(subtotal[0])
            else:
                u.price_subtotal = 0.0

    @api.depends("sub_update_ids", "sub_update_ids.unit_progress", "progress")
    def _is_complete(self):
        self._update_completion_state()

    def _update_completion_state(self):
        for task in self:
            if not task.is_control_obra:
                continue

            if task.approval_state in ["draft", "to_approve", "rejected"]:
                continue

            target_value = task.total_pieces

            # CORRECCIÓN: Ajustar la meta si es subtarea ponderada (Usar total del Padre)
            if task.parent_id and task.parent_id.use_weighted_progress and task.subtask_weight > 0:
                # Meta heredada: Total Padre * Peso Subtarea
                target_value = task.parent_id.total_pieces * \
                    (task.subtask_weight / 100.0)

            current_value = task.quant_progress

            if task.use_weighted_progress:
                target_value = 100.0
                current_value = float(task.progress)

            if target_value == 0:
                continue

            comparison = float_compare(
                current_value, target_value, precision_digits=2)

            if comparison >= 0:
                task.is_complete = True
                task.state = "1_done"
                task.stage_id = self.env.ref(
                    "project_modificaciones.project_task_type_obra_done", raise_if_not_found=False
                )

            elif current_value > 0:
                task.is_complete = False
                if task.approval_state == "approved":
                    stage_pending = self.env.ref(
                        "project_modificaciones.project_task_type_obra_pending",
                        raise_if_not_found=False,
                    )
                    stage_done = self.env.ref(
                        "project_modificaciones.project_task_type_obra_done",
                        raise_if_not_found=False,
                    )

                    if (
                        task.stage_id in [stage_pending, stage_done]
                        or not task.stage_id
                    ):
                        task.stage_id = self.env.ref(
                            "project_modificaciones.project_task_type_obra_progress",
                            raise_if_not_found=False,
                        )
                        task.state = "01_in_progress"

            else:
                task.is_complete = False
                if task.approval_state == "approved":
                    stage_progress = self.env.ref(
                        "project_modificaciones.project_task_type_obra_progress",
                        raise_if_not_found=False,
                    )
                    stage_done = self.env.ref(
                        "project_modificaciones.project_task_type_obra_done",
                        raise_if_not_found=False,
                    )

                    if task.stage_id in [stage_progress, stage_done]:
                        task.stage_id = self.env.ref(
                            "project_modificaciones.project_task_type_obra_pending",
                            raise_if_not_found=False,
                        )
                        task.state = "04_waiting_normal"

    @api.model
    def update_task_status(self):
        tasks = self.env["project.task"].search(
            [("sale_order_id", "!=", False)])
        tasks._update_completion_state()

    def _get_updated_analytic_distribution(self, distribution, new_account_id, old_account_id=False):
        if not new_account_id:
            return distribution or {}

        # Ensure we work with strings as keys
        distribution = distribution or {}
        new_dist = {}
        str_new_id = str(new_account_id)
        str_old_id = str(old_account_id) if old_account_id else False

        replaced = False

        # Odoo 17 supports composite keys like '1,2' for multiple plans
        # We must iterate and check/replace within the keys
        for key, value in distribution.items():
            key_parts = key.split(",")

            if str_old_id and str_old_id in key_parts:
                # Replace old ID with new I in this key
                new_parts = [str_new_id if x ==
                             str_old_id else x for x in key_parts]
                # Reconstruct key (sort order might matter in Odoo, but usually keeping order is safe)
                new_key = ",".join(new_parts)
                new_dist[new_key] = value
                replaced = True
            else:
                new_dist[key] = value

        # If we didn't replace anything, it means the old account wasn't found.
        # If we just force-add the new one, we create double allocation (100% + 100%).
        # Logic: If the distribution was empty, add it.
        # If it wasn't empty but we didn't find the old one, we probably shouldn't mess it up
        # by adding a duplicate 100% line.
        if not replaced and not distribution:
            new_dist[str_new_id] = 100.0

        # If we want to be aggressive (Force New Project Account),
        # we would need to know if we should clear existing.
        # For now, avoiding duplication is the priority based on user feedback.

        return new_dist

    def _handle_project_change(self, prev_data, new_project):
        """
        Handles the logic for when a task changes project.
        Moves related records and updates analytic distributions.
        """
        self.ensure_one()
        old_project = prev_data['project_id']
        old_analytic = prev_data['analytic_account_id']
        sale_order = prev_data['sale_order_id']
        was_done = (prev_data.get('state') == '1_done')

        if not (old_project and new_project and old_project != new_project):
            return

        new_analytic = new_project.analytic_account_id
        if new_analytic and self.analytic_account_id != new_analytic:
            self.write({'analytic_account_id': new_analytic.id})

        # 1. Update Sub Updates (Avances)
        if self.sub_update_ids:
            source_updates = self.sub_update_ids.mapped('update_id')
            avances_by_date = {}
            for avance in self.sub_update_ids:
                avance_date = avance.date or fields.Date.today()
                if avance_date not in avances_by_date:
                    avances_by_date[avance_date] = self.env['project.sub.update']
                avances_by_date[avance_date] |= avance

            for p_date, avances in avances_by_date.items():
                existing_update = self.env['project.update'].search([
                    ('project_id', '=', new_project.id),
                    ('date', '=', p_date)
                ], limit=1)

                if not existing_update:
                    original_update_name = _('Actualización Transferida')
                    if avances and (valid_update_id := avances[0].update_id):
                        original_update_name = valid_update_id.name

                    try:
                        existing_update = self.env['project.update'].create({
                            'project_id': new_project.id,
                            'name': original_update_name,
                            'date': p_date,
                            'user_id': self.env.user.id,
                            'status': 'on_track'
                        })
                    except Exception as e:
                        _logger.warning(
                            "No se pudo crear project.update: %s", str(e))
                        existing_update = False

                vals_avance = {'project_id': new_project.id}
                if existing_update:
                    vals_avance['update_id'] = existing_update.id
                else:
                    vals_avance['update_id'] = False

                avances.write(vals_avance)

            for old_update in source_updates:
                count_remaining = self.env['project.sub.update'].search_count(
                    [('update_id', '=', old_update.id)])
                if count_remaining == 0:
                    old_update.sudo().unlink()

        # 2. Update Child Tasks
        child_tasks = self.search(
            [('parent_id', '=', self.id), ('project_id', '=', old_project.id)])
        if child_tasks:
            child_tasks.write({'project_id': new_project.id})

        # 3. Update Expenses
        if 'expense_ids' in self.env['project.task']._fields:
            all_expenses = self.expense_ids.filtered(
                lambda e: e.state not in ['refused'])  # Removed 'done' from filter to handle locks via code

            expenses_free = all_expenses.filtered(
                lambda e: not e.sheet_id or e.sheet_id.state in ['draft', 'submit'])
            expenses_locked = all_expenses - expenses_free

            if expenses_free:
                vals_expense = {'project_id': new_project.id}
                if new_analytic:
                    for expense in expenses_free:
                        new_dist = self._get_updated_analytic_distribution(
                            expense.analytic_distribution, new_analytic.id, old_analytic.id
                        )
                        expense.sudo().write({
                            'project_id': new_project.id,
                            'analytic_distribution': new_dist
                        })
                else:
                    expenses_free.sudo().write(vals_expense)

            if expenses_locked:
                for exp in expenses_locked:
                    vals_locked = {'project_id': new_project.id}
                    if new_analytic:
                        new_dist = self._get_updated_analytic_distribution(
                            exp.analytic_distribution, new_analytic.id, old_analytic.id
                        )
                        vals_locked['analytic_distribution'] = new_dist

                    # Usamos sudo() para saltar restricciones de estado si es posible
                    exp.sudo().write(vals_locked)

        # 4. Update Purchase Orders
        purchase_orders = self.env['purchase.order'].search([
            ('task_order_id', '=', self.id),
            ('state', '!=', 'cancel')
        ])

        if purchase_orders:
            purchase_orders.write({'project_id': new_project.id})
            lines_to_update = purchase_orders.mapped('order_line').filtered(
                lambda l: l.state != 'cancel'
            )
            if lines_to_update:
                vals_line = {
                    'project_id': new_project.id,
                    'task_id': self.id
                }
                if new_analytic:
                    for line in lines_to_update:
                        dist = self._get_updated_analytic_distribution(
                            line.analytic_distribution, new_analytic.id, old_analytic.id)
                        line_vals = vals_line.copy()
                        line_vals['analytic_distribution'] = dist
                        line.write(line_vals)
                else:
                    lines_to_update.write(vals_line)

            pickings = purchase_orders.mapped('picking_ids').filtered(
                lambda p: p.state != 'cancel'
            )
            if pickings:
                pickings.write({
                    'project_id': new_project.id,
                    'task_id': self.id
                })
                moves = pickings.mapped('move_ids').filtered(
                    lambda m: m.state != 'cancel'
                )
                if moves:
                    moves.write({
                        'project_id': new_project.id,
                        'task_id': self.id
                    })

        # 5. Update Independent Purchase Lines
        if 'purchase_line_ids' in self.env['project.task']._fields:
            processed_orders = purchase_orders.ids if purchase_orders else []
            purchase_lines = self.purchase_line_ids.filtered(
                lambda l: l.state not in ['cancel', 'done'] and l.order_id.id not in processed_orders)

            if purchase_lines:
                vals_line_loose = {'project_id': new_project.id}
                if new_analytic:
                    for line in purchase_lines:
                        new_dist_line = self._get_updated_analytic_distribution(
                            line.analytic_distribution, new_analytic.id, old_analytic.id
                        )
                        curr_vals = vals_line_loose.copy()
                        curr_vals['analytic_distribution'] = new_dist_line
                        line.write(curr_vals)
                else:
                    purchase_lines.write(vals_line_loose)

        # 6. Update Timesheets
        if 'timesheet_ids' in self.env['project.task']._fields:
            timesheets_model = self.env['account.analytic.line']
            if 'timesheet_invoice_id' in timesheets_model._fields:
                timesheets = self.timesheet_ids.filtered(
                    lambda t: not t.timesheet_invoice_id)
            else:
                timesheets = self.timesheet_ids

            if timesheets:
                ts_vals = {'project_id': new_project.id}
                if self.sale_line_id:
                    ts_vals['so_line'] = self.sale_line_id.id
                timesheets.write(ts_vals)

        # 7. Update Stock Moves (Direct)
        if 'stock_move_ids' in self.env['project.task']._fields:
            moves_to_update = self.stock_move_ids
            if moves_to_update:
                moves_to_update.write(
                    {'project_id': new_project.id})

        self.env['project.sub.update'].invalidate_model()
        self.invalidate_recordset()

        self._units()
        current_quant = self.quant_progress

        total_qty = 0.0
        if self.sale_line_id:
            linea = self.env['sale.order.line'].browse(
                self.sale_line_id.id)
            total_qty = linea.product_uom_qty

        new_progress = 0
        new_pct = 0.0

        if total_qty > 0 and current_quant > 0:
            new_progress_float = (current_quant / total_qty) * 100
            new_progress = min(100, int(new_progress_float))
            new_pct = new_progress_float / 100.0

        self.sudo().write({
            'progress': new_progress,
            'progress_percentage': new_pct
        })

        if self.sale_line_id:
            self.sale_line_id.sudo().write(
                {'qty_delivered': current_quant})

        # 8. Update Requisitions
        if 'requisition_ids' in self.env['project.task']._fields:
            requisitions_to_move = self.requisition_ids.filtered(
                lambda r: r.state not in ['cancel']
            )

            for req in requisitions_to_move:
                req_vals = {}
                if 'project_id' in self.env['employee.purchase.requisition']._fields:
                    req_vals['project_id'] = new_project.id

                if 'analytic_distribution' in self.env['employee.purchase.requisition']._fields and new_analytic:
                    curr_dist = req.analytic_distribution if hasattr(
                        req, 'analytic_distribution') else {}
                    req_vals['analytic_distribution'] = self._get_updated_analytic_distribution(
                        curr_dist, new_analytic.id, old_analytic.id
                    )

                if req_vals:
                    req.write(req_vals)

                if hasattr(req, 'requisition_order_ids') and req.requisition_order_ids:
                    lines_req = req.requisition_order_ids
                    if 'project_id' in self.env['requisition.order']._fields:
                        lines_req.write(
                            {'project_id': new_project.id})

                    if 'analytic_distribution' in self.env['requisition.order']._fields and new_analytic:
                        for l_req in lines_req:
                            dist_req = self._get_updated_analytic_distribution(
                                l_req.analytic_distribution, new_analytic.id, old_analytic.id)
                            l_req.write(
                                {'analytic_distribution': dist_req})

        # 9. Update Attendance
        attendance_model = self.env.get(
            'attendance.regularization')
        if attendance_model is not None and 'task_id' in attendance_model._fields:
            attendance_recs = attendance_model.search([
                ('task_id', '=', self.id)
            ])
            if attendance_recs and 'project_id' in attendance_model._fields:
                attendance_recs.write(
                    {'project_id': new_project.id})

        # 10. Update Compensation
        comp_line_model = self.env.get('compensation.line')
        if comp_line_model is not None and 'task_id' in comp_line_model._fields:
            comp_lines = comp_line_model.search(
                [('task_id', '=', self.id)])

            if comp_lines:
                if 'project_id' in comp_line_model._fields:
                    comp_lines.write(
                        {'project_id': new_project.id})

                comp_requests = comp_lines.mapped(
                    'compensation_id')
                for req in comp_requests:
                    if 'unique_project' in req._fields and 'service' in req._fields:
                        if req.unique_project:
                            if req.service != new_project:
                                req.write(
                                    {'service': new_project.id})

        # 11. Update Sale Order
        if sale_order and sale_order.project_id == old_project:
            tasks_remaining_all = self.with_context(active_test=False).search_count([
                ('project_id', '=', old_project.id),
                ('sale_order_id', '=', sale_order.id)
            ])

            if tasks_remaining_all == 0:
                sale_order.sudo().write(
                    {'project_id': new_project.id})
            else:
                active_tasks = self.search_count([
                    ('project_id', '=', old_project.id),
                    ('sale_order_id', '=', sale_order.id)
                ])

                if active_tasks == 0 and tasks_remaining_all > 0:
                    archived_tasks = self.with_context(active_test=False).search([
                        ('project_id', '=', old_project.id),
                        ('sale_order_id', '=', sale_order.id)
                    ])
                    archived_tasks.write(
                        {'project_id': new_project.id})
                    sale_order.sudo().write(
                        {'project_id': new_project.id})

        # 12. Restore Done State
        if was_done and self.state != '1_done':
            stage_done = self.env.ref(
                "project_modificaciones.project_task_type_obra_done", raise_if_not_found=False)
            vals_restore = {
                'state': '1_done',
                'is_complete': True,
                'progress': 100,
                'progress_percentage': 1.0,
            }
            if stage_done:
                vals_restore['stage_id'] = stage_done.id
            self.sudo().write(vals_restore)
            if self.sale_line_id:
                self.sale_line_id.sudo().write(
                    {'qty_delivered': self.total_pieces})

    def write(self, vals):
        old_state = {
            task.id: {
                'project_id': task.project_id,
                'state': task.state,
                'analytic_account_id': task.analytic_account_id or task.project_id.analytic_account_id,
                'sale_order_id': task.sale_order_id
            } for task in self
        }

        res = super(Task, self).write(vals)

        if "project_id" in vals:
            self._compute_is_control_obra()
            new_project_id = vals.get('project_id')
            new_project = self.env['project.project'].browse(
                new_project_id) if new_project_id else self.env['project.project']

            for task in self:
                prev_data = old_state.get(task.id)
                if prev_data:
                    task._handle_project_change(prev_data, new_project)

        self.env.invalidate_all()
        return res

    def _compute_updates_count(self):
        for task in self:
            count = 0
            if task.use_weighted_progress and task.child_ids:
                count = self.env['project.sub.update'].search_count([
                    ('task_id', 'in', task.child_ids.ids + [task.id])
                ])
            else:
                count = len(task.sub_update_ids)
            task.updates_count = count

    updates_count = fields.Integer(compute='_compute_updates_count')

    def action_view_avances(self):
        self.ensure_one()
        domain = [("task_id", "=", self.id)]

        if self.use_weighted_progress and self.child_ids:
            domain = [("task_id", "in", self.child_ids.ids + [self.id])]

        return {
            "name": _("Avances de la Tarea"),
            "type": "ir.actions.act_window",
            "res_model": "project.sub.update",
            "view_mode": "list,form",
            "domain": domain,
            "context": {
                "default_task_id": self.id,
                "default_project_id": self.project_id.id,
                "create": True,
                "delete": True,
            },
            "flags": {"creatable": True},
            "target": "current",
        }

    def _compute_counts(self):
        for task in self:
            task.expense_count = len(task.expense_ids)
            task.purchase_count = len(
                task.purchase_line_ids.mapped("order_id"))
            task.requisition_count = len(task.requisition_ids)
            task.stock_move_count = len(task.stock_move_ids)

    def _compute_totals(self):
        for task in self:
            approved_expenses = task.expense_ids.filtered(
                lambda e: e.sheet_id.state in ["post", "done"]
            )
            task.expense_total_approved = sum(
                approved_expenses.mapped("total_amount"))

            confirmed_lines = task.purchase_line_ids.filtered(
                lambda l: l.order_id.state in ["purchase", "done"]
            )
            task.purchase_total_approved = sum(
                confirmed_lines.mapped("price_subtotal"))

    def action_view_expenses(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Gastos",
            "res_model": "hr.expense",
            "view_mode": "list,kanban,form",
            "domain": [("task_id", "=", self.id)],
            "context": {"default_task_id": self.id},
        }

    def action_view_purchases(self):
        self.ensure_one()
        purchase_lines = self.env["purchase.order.line"].search(
            [("task_id", "=", self.id)]
        )
        purchase_orders = purchase_lines.mapped("order_id")
        return {
            "type": "ir.actions.act_window",
            "name": "Órdenes de compra",
            "res_model": "purchase.order",
            "view_mode": "list,kanban,form",
            "domain": [("id", "in", purchase_orders.ids)],
            "context": {"default_task_order_id": self.id},
        }

    def action_view_requisitions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Requisiciones",
            "res_model": "employee.purchase.requisition",
            "view_mode": "tree,form,kanban",
            "domain": [("task_id", "=", self.id)],
            "context": {"default_task_id": self.id, "default_project_id": self.project_id.id},
        }

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.partner_id.centro_trabajo:
                self.centro_trabajo = self.partner_id.centro_trabajo
            else:
                self.centro_trabajo = False

    @api.depends("project_id", "project_id.is_proyecto_obra")
    def _compute_is_control_obra(self):
        for control in self:
            control.is_control_obra = bool(control.project_id.is_proyecto_obra)

    @api.model
    def default_get(self, fields_list):
        defaults = super(Task, self).default_get(fields_list)

        project_id = defaults.get("project_id") or self.env.context.get(
            "default_project_id"
        )

        if project_id:
            project = self.env["project.project"].browse(project_id)

            if project.is_proyecto_obra:
                defaults["is_control_obra"] = True
            else:
                defaults["is_control_obra"] = False
        return defaults

    @api.depends("approver_id")
    def _compute_can_user_approve(self):
        is_global_approver = self.env.user.has_group(
            'project_modificaciones.permiso_global_aprobar_tarea')

        for task in self:
            if is_global_approver:
                task.can_user_approve = True
            elif task.approver_id:
                task.can_user_approve = (self.env.user == task.approver_id)
            else:
                task.can_user_approve = False

    @api.onchange("centro_trabajo")
    def _onchange_centro_trabajo(self):
        if (
            self.planta_trabajo
            and self.planta_trabajo.cliente != self.centro_trabajo.cliente
        ):
            self.planta_trabajo = False

        if (
            self.supervisor_cliente
            and self.supervisor_cliente.cliente != self.centro_trabajo.cliente
        ):
            self.supervisor_cliente = False

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            if vals.get("sale_line_id"):
                line = self.env["sale.order.line"].browse(vals["sale_line_id"])

                if line.order_id.pending_service_id:
                    vals["name"] = f"{line.order_id.name}: {line.name}"
                elif line.partida:
                    original_name = vals.get("name", "")
                    if line.partida not in original_name:
                        vals["name"] = f"{original_name}-[{line.partida}]"

        stage_draft = self.env.ref(
            "project_modificaciones.project_task_type_obra_draft", raise_if_not_found=False
        )

        project_ids = [v.get("project_id")
                       for v in vals_list if v.get("project_id")]

        project_map = {
            p["id"]: p["is_proyecto_obra"]
            for p in self.env["project.project"]
            .browse(project_ids)
            .read(["is_proyecto_obra"])
        }

        for vals in vals_list:
            is_control_obra = vals.get("is_control_obra", None)

            if is_control_obra is None:
                project_id = vals.get("project_id")
                is_control_obra = project_map.get(project_id, False)
                vals["is_control_obra"] = is_control_obra

            if is_control_obra:
                initial_approval = "draft"
                initial_stage = stage_draft.id if stage_draft else vals.get(
                    "stage_id")

                if vals.get("parent_id"):
                    parent_task = self.env["project.task"].browse(
                        vals["parent_id"])
                    if parent_task.approval_state == "approved":
                        initial_approval = "approved"
                        stage_progress = self.env.ref(
                            "project_modificaciones.project_task_type_obra_progress", raise_if_not_found=False
                        )
                        if stage_progress:
                            initial_stage = stage_progress.id

                    fields_to_inherit = [
                        'partner_id',
                        'supervisor_interno',
                        'supervisor_cliente',
                        'centro_trabajo',
                        'planta_trabajo'
                    ]
                    for field in fields_to_inherit:
                        if (field not in vals or not vals.get(field)) and parent_task[field]:
                            vals[field] = parent_task[field].id

                vals.update({
                    "approval_state": initial_approval,
                    "stage_id": initial_stage,
                })

                supervisor_interno_id = vals.get("supervisor_interno")

                if supervisor_interno_id:
                    supervisor = self.env["hr.employee"].sudo().browse(
                        supervisor_interno_id)
                    approver_user_id = False

                    if supervisor.apropador_tarea_obra:
                        approver_user_id = supervisor.apropador_tarea_obra.user_id.id

                    if not approver_user_id:
                        approver_employee = supervisor.parent_id

                        if not approver_employee:
                            raise ValidationError(_(
                                "El supervisor %s no tiene configurado un 'Aprobador de Tarea Obra' ni un 'Líder directo'."
                            ) % supervisor.name)

                        if not approver_employee.user_id:
                            raise ValidationError(_(
                                "El Gerente %s del Supervisor %s no tiene usuario asociado."
                            ) % (approver_employee.name, supervisor.name))

                        approver_user_id = approver_employee.user_id.id

                    vals["approver_id"] = approver_user_id

        tasks = super(Task, self).create(vals_list)

        for task in tasks:
            if task.is_control_obra and stage_draft and task.stage_id != stage_draft:
                task.sudo().write({"stage_id": stage_draft.id})

        return tasks

    def _create_approval_activity(self):
        activity_type_per = self.env.ref(
            "project_modificaciones.aprobacion_mail_activity", raise_if_not_found=False
        )
        if not activity_type_per:
            activity_type_per = self.env.ref(
                "mail.mail_activity_data_todo", raise_if_not_found=False
            )

        for task in self:
            if task.approver_id and task.approval_state == "to_approve":
                activity = self.env["mail.activity"].create(
                    {
                        "res_model_id": self.env.ref("project.model_project_task").id,
                        "res_id": task.id,
                        "user_id": task.approver_id.id,
                        "activity_type_id": activity_type_per.id,
                        "summary": _("Aprobar Tarea de Obra: %s") % task.name,
                        "note": _(
                            "Por favor, revisa y aprueba esta tarea de obra (%s) creada por %s."
                        )
                        % (task.name, task.create_uid.name),
                    }
                )
                task.approval_activity_id = activity.id

    def _mark_approval_activity_done(self):
        for task in self:
            if task.approval_activity_id:
                selection_dict = dict(task._fields["approval_state"].selection)
                state_label = (
                    selection_dict.get(
                        task.approval_state) or task.approval_state
                )
                task.approval_activity_id.action_feedback(
                    feedback=_("Decisión tomada: %s") % state_label
                )

    def action_send_for_approval(self):
        stage_to_approve = self.env.ref(
            "project_modificaciones.project_task_type_obra_to_approve", raise_if_not_found=False
        )

        for task in self:
            if task.parent_id and task.parent_id.approval_state == 'approved':
                stage_progress = self.env.ref(
                    "project_modificaciones.project_task_type_obra_progress", raise_if_not_found=False)
                task.with_context(tracking_disable=True).write({
                    "approval_state": "approved",
                    "state": "01_in_progress",
                    "stage_id": stage_progress.id if stage_progress else task.stage_id.id
                })
                task.message_post(
                    body=Markup(
                        "✅ <b>AUTO-APROBADA</b><br/>Heredada de Tarea Padre: %s") % task.parent_id.name,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
                continue

            if not task.supervisor_interno:
                raise ValidationError(
                    _("Debe especificar un Supervisor Interno."))

            supervisor = task.supervisor_interno.sudo()
            approver_user = False

            if supervisor.apropador_tarea_obra:
                approver_user = supervisor.apropador_tarea_obra.user_id

            if not approver_user:
                approver_employee = supervisor.parent_id
                if not approver_employee:
                    raise ValidationError(
                        _("El Supervisor Interno no tiene configurado un aprobador ni un líder directo."))
                if not approver_employee.user_id:
                    raise ValidationError(
                        _("El líder directo del supervisor no tiene un usuario asociado."))
                approver_user = approver_employee.user_id

            if not approver_user.partner_id:
                raise ValidationError(
                    _("El usuario aprobador (%s) no tiene un partner configurado.") % approver_user.name)

            vals = {
                "approval_state": "to_approve",
                "approver_id": approver_user.id,
            }
            if stage_to_approve:
                vals["stage_id"] = stage_to_approve.id

            task.with_context(tracking_disable=True).write(vals)
            task._create_approval_activity()

            msg = (
                Markup(
                    "⚠️ <b>SOLICITUD DE APROBACIÓN</b><br/>"
                    "El supervisor <b>%s</b> solicita revisión.<br/>"
                    "Aprobador asignado: <b>%s</b>"
                ) % (task.supervisor_interno.name, approver_user.name)
            )

            task.message_post(
                body=msg,
                subject="Aprobación Requerida",
                message_type="notification",
                subtype_xmlid="mail.mt_note",
                partner_ids=[approver_user.partner_id.id],
            )

    def action_approve(self):
        stage_approved = self.env.ref(
            "project_modificaciones.project_task_type_obra_approved", raise_if_not_found=False)
        stage_progress = self.env.ref(
            "project_modificaciones.project_task_type_obra_progress", raise_if_not_found=False)
        target_stage = stage_progress or stage_approved or self.env["project.task.type"]

        is_global = self.env.user.has_group(
            'project_modificaciones.permiso_global_aprobar_tarea')

        for task in self:
            if task.approval_state != "to_approve":
                continue
            if self.env.user != task.approver_id and not is_global:
                raise ValidationError(
                    _("Solo el aprobador asignado o un aprobador global pueden aprobar."))

            recipient_ids = []
            if task.supervisor_interno.user_id:
                recipient_ids.append(
                    task.supervisor_interno.user_id.partner_id.id)

            if task.approval_activity_id and task.approval_activity_id.create_uid:
                recipient_ids.append(
                    task.approval_activity_id.create_uid.partner_id.id)

            recipient_ids = list(set(recipient_ids))

            vals = {
                "approval_state": "approved",
                "state": "01_in_progress",
            }
            if target_stage:
                vals["stage_id"] = target_stage.id

            task.with_context(tracking_disable=True).write(vals)
            task._mark_approval_activity_done()

            task.message_post(
                body=Markup(
                    "✅ <b>TAREA APROBADA</b><br/>Autorizado por: %s") % self.env.user.name,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
                partner_ids=recipient_ids,
            )

    def action_reject(self):
        is_global = self.env.user.has_group(
            'project_modificaciones.permiso_global_aprobar_tarea')
        for task in self:
            if task.approval_state != "to_approve":
                continue
            if self.env.user != task.approver_id and not is_global:
                raise ValidationError(
                    _("Solo el aprobador asignado (%s) o un aprobador global pueden rechazar.") % task.approver_id.name)

            return {
                "type": "ir.actions.act_window",
                "res_model": "wizard.rechazado.task",
                "view_mode": "form",
                "target": "new",
                "context": {"active_id": task.id},
            }

    def action_draft(self):
        is_global = self.env.user.has_group(
            'project_modificaciones.permiso_global_aprobar_tarea')
        stage_to_draft = self.env.ref(
            "project_modificaciones.project_task_type_obra_draft", raise_if_not_found=False)
        for task in self:
            if task.approval_state != "rejected":
                continue
            if self.env.user != task.approver_id and not is_global:
                raise ValidationError(
                    _("Solo el aprobador asignado (%s) o un aprobador global pueden regresar a borrador.") % task.approver_id.name)

            task.with_context(tracking_disable=True).write({
                "approval_state": "draft",
                "stage_id": stage_to_draft.id if stage_to_draft else task.stage_id.id,
            })

    def notify_rejection(self, motivo):
        for task in self:
            recipient_ids = []
            if task.supervisor_interno.user_id:
                recipient_ids.append(
                    task.supervisor_interno.user_id.partner_id.id)

            if task.approval_activity_id and task.approval_activity_id.create_uid:
                recipient_ids.append(
                    task.approval_activity_id.create_uid.partner_id.id)

            recipient_ids = list(set(recipient_ids))

            msg_body = (
                Markup(
                    "🛑 <b> TAREA RECHAZADA </b><br/>"
                    "<b> Motivo: </b>%s<br/>"
                    "Por favor corrige y vuelve a enviar la tarea a aprobación."
                )
                % motivo
            )

            task.message_post(
                body=msg_body,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
                partner_ids=recipient_ids,
            )

    @api.constrains('child_ids', 'use_weighted_progress')
    def _check_subtask_weights(self):
        for task in self:
            if task.use_weighted_progress and task.child_ids:
                total_weight = sum(task.child_ids.mapped('subtask_weight'))
                # Se permite que la suma sea menor o igual a 100%
                # El remanente lo gestiona la tarea padre directamente.
                if total_weight > 100.1:
                    raise ValidationError(_(
                        "La suma de los pesos de las subtareas no puede exceder el 100%%. "
                        "Suma actual: %s%% en la tarea %s"
                    ) % (total_weight, task.name))
