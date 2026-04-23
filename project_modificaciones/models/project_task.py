<<<<<<< HEAD
from odoo import fields, models, api, _
from markupsafe import Markup
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
import logging
import json
=======
import json
import logging
from markupsafe import Markup
from datetime import datetime
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)

_logger = logging.getLogger(__name__)


class Task(models.Model):
    _inherit = 'project.task'

<<<<<<< HEAD
    # ========== CAMPOS DE INTEGRACIÓN CON VENTAS ==========
    sale_line_id = fields.Many2one(
        "sale.order.line",
        "Línea de Orden de Venta",
        copy=False,
        index=True,
        ondelete='set null',
        help="Línea de orden de venta asociada a esta tarea. Solo se muestran servicios confirmados."
    )

    # Habilitar tracking para cambios de proyecto
    project_id = fields.Many2one(tracking=True)

    # Estados personalizados de tarea
    state = fields.Selection(
        selection_add=[
            ("01_in_progress", "En Progreso"),
            ("1_done", "Terminado"),
            ("04_waiting_normal", "En Espera"),
=======
    planned_date_begin = fields.Datetime(
        string="Start date",
        related="date_assign",
        store=True,
        readonly=False,
        help="Compatibilidad para módulos que esperan una fecha de inicio planeada en project.task.",
    )

    """
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sales Order Item',
        copy=False,
        compute="_compute_sale_line_id",
        store=True,
        readonly=False,
        index='btree_not_null',
        domain="[('is_service', '=', True), ('is_expense', '=', False), ('state', 'in', ['sale', 'done']), ('order_partner_id', '=?', partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Sales order line linked to this task. Used to synchronize progress with the sale order line."
    )"""

    project_id = fields.Many2one(tracking=True)

    state = fields.Selection(
        selection_add=[
            ("01_in_progress", "In Progress"),
            ("1_done", "Done"),
            ("04_waiting_normal", "Waiting"),
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        ],
        ondelete={
            "04_waiting_normal": "set default",
            "01_in_progress": "set default",
            "1_done": "set default",
        },
    )

    sale_order_id = fields.Many2one(
<<<<<<< HEAD
        string="Orden de Venta",
        related="sale_line_id.order_id",
        help="Orden de venta a la cual está vinculada la tarea.",
    )

    # Campos relacionados con la orden de venta
    delivered = fields.Float(
        string="Entregado",
        related="sale_line_id.qty_delivered",
        help="Cantidad entregada en la línea de orden de venta."
    )
    price_unit = fields.Float(
        string="Precio Unitario",
        related="sale_line_id.price_unit",
        help="Precio unitario del servicio en la orden de venta."
    )
    total_pieces = fields.Float(
        string="Piezas/Servicio (total)",
        related="sale_line_id.product_uom_qty",
        store=True,
        readonly=True,
        help="Cantidad total de unidades/servicios contratados en la orden de venta."
    )
    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_subtotal",
        store=True,
        help="Subtotal calculado del servicio."
    )
    qty_invoiced = fields.Float(
        string="Facturado (unidades)",
        related="sale_line_id.qty_invoiced",
        store=False,
        help="Cantidad de unidades ya facturadas."
    )
    disc = fields.Many2one(
        string="Especialidad",
        related="sale_line_id.product_id.categ_id",
        store=False,
        help="Categoría/especialidad del producto/servicio."
    )
    invoiced = fields.Float(
        string="Facturado",
        compute="_invoiced",
        store=False,
        help="Monto total facturado de esta tarea."
    )
    # ========== FIN CAMPOS DE INTEGRACIÓN CON VENTAS ==========

    # ========== CAMPOS DE ANALYTICS_EXTRA (mod_task.py) ==========
=======
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
    # Moneda de compañía (para mostrar totales)
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Moneda",
        store=True,
        readonly=True,
    )
<<<<<<< HEAD
    expense_ids = fields.One2many("hr.expense", "task_id", string="Gastos")
    purchase_ids = fields.One2many(
        "purchase.order", "task_order_id", string="Compras")
    purchase_line_ids = fields.One2many(
        "purchase.order.line", "task_id", string="Líneas de compra"
    )
=======
    # Gastos asociados a la tarea
    expense_ids = fields.One2many("hr.expense", "task_id", string="Gastos")
    # Órdenes de compra asociadas a la tarea (legado)
    purchase_ids = fields.One2many(
        "purchase.order", "task_order_id", string="Compras")
    # Líneas de compra asociadas a la tarea (fuente de verdad)
    purchase_line_ids = fields.One2many(
        "purchase.order.line", "task_id", string="Líneas de compra"
    )
    # Requisiciones asociadas a la tarea
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    requisition_ids = fields.One2many(
        "employee.purchase.requisition", "task_id", string="Requisiciones"
    )

<<<<<<< HEAD
    # Relación con servicios pendientes
    pending_service_line_ids = fields.One2many(
        "pending.service.line",
        "task_id",
        string="Líneas de Servicio Pendiente",
        help="Líneas de servicio pendiente asociadas a esta tarea."
    )

    expense_count = fields.Integer(string="Gastos", compute="_compute_counts")
    purchase_count = fields.Integer(
        string="Compras", compute="_compute_counts")
    requisition_count = fields.Integer(
        string="Requisiciones", compute="_compute_counts")
    stock_move_count = fields.Integer(
        string="Movimientos de Almacén", compute="_compute_counts")

=======
    # Contadores rápidos
    expense_count = fields.Integer(
        string="Cant. Gastos", compute="_compute_counts")
    purchase_count = fields.Integer(
        string="Cant. Compras", compute="_compute_counts")
    requisition_count = fields.Integer(
        string="Cant. Requisiciones", compute="_compute_counts")
    stock_move_count = fields.Integer(
        string="Cant. Movimientos de Almacén", compute="_compute_counts")

    # Total de gastos aprobados (aprobado/posteado)
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    expense_total_approved = fields.Monetary(
        string="Total gastos (aprobados)",
        compute="_compute_totals",
        currency_field="currency_id",
        store=False,
    )
<<<<<<< HEAD
=======
    # Total de compras confirmadas (sin impuestos)
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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
<<<<<<< HEAD
        # Prefetch purchase lines for all tasks in self
        all_purchase_lines = self.env['purchase.order.line'].search([
            ('task_id', 'in', self.ids),
            ('order_id.state', 'in', ['purchase', 'done'])
        ])

        # Group purchase lines by task_id and then by product_id
        purchase_lines_by_task = {}
        for line in all_purchase_lines:
            task_id = line.task_id.id
            if task_id not in purchase_lines_by_task:
                purchase_lines_by_task[task_id] = {}

            product_id = line.product_id.id
            purchase_lines_by_task[task_id][product_id] = \
                purchase_lines_by_task[task_id].get(
                    product_id, 0.0) + line.product_qty

        for task in self:
            cost = 0.0
            moves = task.stock_move_ids.filtered(lambda m: m.state == 'done')

=======
        for task in self:
            cost = 0.0

            # 1. Obtener cantidades movidas por producto (Solo Salidas/Outgoing y Done)
            moves = task.stock_move_ids.filtered(lambda m: m.state == 'done')

            # Map Product -> Total Qty Moved
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            moved_qty_per_product = {}
            for move in moves:
                qty = move.quantity
                moved_qty_per_product[move.product_id.id] = moved_qty_per_product.get(
                    move.product_id.id, 0.0) + qty

<<<<<<< HEAD
            purchased_qty_per_product = purchase_lines_by_task.get(task.id, {})

            for product_id, moved_qty in moved_qty_per_product.items():
                purchased_qty = purchased_qty_per_product.get(product_id, 0.0)
                chargeable_qty = max(0.0, moved_qty - purchased_qty)

                if chargeable_qty > 0:
                    product = task.env['product.product'].browse(product_id)
                    unit_cost = product.standard_price
                    cost += chargeable_qty * unit_cost

            task.stock_move_cost = cost
    # ========== FIN CAMPOS DE INTEGRACIÓN ALMACÉN ==========

=======
            # 2. Obtener cantidades compradas por producto (Solo Confirmadas)
            purchased_qty_per_product = {}
            purchase_lines = task.purchase_line_ids.filtered(
                lambda line: line.order_id.state in ['purchase', 'done']
            )
            for line in purchase_lines:
                purchased_qty_per_product[line.product_id.id] = purchased_qty_per_product.get(
                    line.product_id.id, 0.0) + line.product_qty

            # 3. Lógica de Cobro Neto
            for product_id, moved_qty in moved_qty_per_product.items():
                purchased_qty = purchased_qty_per_product.get(product_id, 0.0)
                chargeable_qty = max(0.0, moved_qty - purchased_qty)
                if chargeable_qty > 0:
                    move_product = moves.filtered(lambda move: move.product_id.id == product_id)[:1].product_id
                    cost += chargeable_qty * (move_product.standard_price or 0.0)

            task.stock_move_cost = cost

    # ---------------------------------------------------------------------
    # Sync task progress with linked Sale Order Line
    # ---------------------------------------------------------------------
    def action_link_sale_line(self):
        """Placeholder method for the "Vincular línea" button.
        Currently does nothing but returns True to avoid errors.
        You can replace it with a proper wizard later.
        """
        self.ensure_one()
        return True    # ========== FIN CAMPOS DE INTEGRACIÓN ALMACÉN ==========

    # Campos originales de control_obra
    # NOTA: Se cambia 'creacion.avances' por 'project.sub.update' para mantener la integridad con el paso anterior
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    sub_update_ids = fields.One2many(
        "project.sub.update",
        "task_id",
        domain="[('project_id', '=', project_id), ('task_id.id', '=', id)]",
        string="Actualización de tareas",
    )
<<<<<<< HEAD

    sub_update = fields.Many2one(
        "project.sub.update", compute="_last_update", store=False)

    @api.depends("sub_update_ids")
    def _last_update(self):
        # Fetch all relevant updates for the tasks in current recordset
        # FIXED: Removed project_id filter to avoid cross-contamination
        updates = self.env["project.sub.update"].search([
            ("task_id", "in", self.ids)
        ], order="id desc")

        # Create a map of task_id -> latest_update (full record)
        latest_updates = {}
        for update in updates:
            # Since updates are ordered by id desc, the first one we encounter for a task is the latest
            if update.task_id.id not in latest_updates:
                latest_updates[update.task_id.id] = update

        for u in self:
            if not u.id or isinstance(u.id, models.NewId):
                u.sub_update = False
                continue

            last_record = latest_updates.get(u.id)
            u.sub_update = last_record or False

    last_update = fields.Many2one(
        "project.update", related="sub_update.update_id", string="Última actualización"
    )

=======
    sub_update = fields.Many2one(
        "project.sub.update", compute="_last_update", store=True)
    last_update = fields.Many2one(
        "project.update", related="sub_update.update_id", string="Última actualización"
    )
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    sub_d_update = fields.Many2one(
        "project.sub.update",
        compute="_d_update",
        string="Última actualización de tarea",
<<<<<<< HEAD
        store=False,
    )

    @api.depends("sub_update_ids")
    def _d_update(self):
        # Fetch all relevant updates for the tasks in current recordset
        # FIXED: Removed project_id filter to avoid cross-contamination
        updates = self.env["project.sub.update"].search([
            ("task_id", "in", self.ids)
        ], order="id desc")

        # Create a map of task_id -> latest_update (full record)
        latest_updates = {}
        for update in updates:
            if update.task_id.id not in latest_updates:
                latest_updates[update.task_id.id] = update

        for u in self:
            if not u.id or isinstance(u.id, models.NewId):
                u.sub_d_update = False
                continue

            last_record = latest_updates.get(u.id)
            u.sub_d_update = last_record or False

=======
        store=True,
    )
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    last_d_update = fields.Many2one(
        "project.update",
        related="sub_d_update.update_id",
        string="Última actualización modificada",
    )
<<<<<<< HEAD
=======
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
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)

    centro_trabajo = fields.Many2one(
        "control.centro.trabajo",
        string="Centro Trabajo",
<<<<<<< HEAD
        ondelete='set null',
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        help="Centro de trabajo en donde se realizara el servicio.",
        tracking=True,
    )

    planta_trabajo = fields.Many2one(
        "control.planta",
        string="Planta",
<<<<<<< HEAD
        ondelete='set null',
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        help="Planta de trabajo en donde se realizara el servicio.",
        tracking=True,
    )

    supervisor_interno = fields.Many2one(
        "hr.employee",
        string="Supervisor Interno",
        domain="[('supervisa', '=', True)]",
<<<<<<< HEAD
        ondelete='set null',
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        help="Supervisor Del Trabajo Interno (AYASA)",
        tracking=True,
    )

    supervisor_cliente = fields.Many2one(
        "supervisor.area",
        string="Supervisor Cliente",
<<<<<<< HEAD
        ondelete='set null',
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        help="Supervisor por parte del cliente al cual se le proporcionara el servicio.",
        tracking=True,
    )

    partida_relacionada = fields.Char(
        string="Partida",
        help="Partida relacionada con la tarea.",
        related="sale_line_id.partida",
        tracking=True,
    )

<<<<<<< HEAD
    tarea_padre = fields.Many2one(
        'project.task',
        related="parent_id",
        string="Tarea Padre",
        help="Muestra la tarea padre si es una subtarea.",
        readonly=True,
    )

=======
    # Campo para indicar que la tarea fue creada desde el modelo control de obra.
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    is_control_obra = fields.Boolean(
        string="Tarea Control Obra",
        default=False,
        compute="_compute_is_control_obra",
        help="Indica que esta tarea es un servicio a realizar, relacionada a un proyecto de obra dentro del modulo Control Obra.",
<<<<<<< HEAD
        store=False,
    )

=======
        store=True,
    )

    # Campo auxiliar invisible para controlar el filtro
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    project_domain_string = fields.Char(
        compute="_compute_project_domain_string",
        readonly=True,
        store=False
    )

    @api.depends('is_control_obra', 'company_id')
    def _compute_project_domain_string(self):
        for task in self:
<<<<<<< HEAD
=======
            # 1. Lógica base (Activos + Compañía)
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            domain = [('active', '=', True)]
            if task.company_id:
                domain += ['|', ('company_id', '=', False),
                           ('company_id', '=', task.company_id.id)]
            else:
                domain += ['|', ('company_id', '=', False),
                           ('company_id', '!=', False)]

<<<<<<< HEAD
            if task.is_control_obra:
                domain.append(('is_proyecto_obra', '=', True))

=======
            # 2. Tu lógica: Si es Control de Obra, filtramos
            if task.is_control_obra:
                domain.append(('is_proyecto_obra', '=', True))

            # 3. Convertimos la lista a string para que el XML la entienda
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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
<<<<<<< HEAD
        ondelete='set null',
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        tracking=True,
        readonly=True,
    )

    approval_activity_id = fields.Many2one(
        "mail.activity",
        string="Actividad de Aprobación",
        copy=False,
<<<<<<< HEAD
        ondelete='set null',
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    )

    can_user_approve = fields.Boolean(
        string="Usuario actual puede aprobar",
        compute="_compute_can_user_approve",
    )

<<<<<<< HEAD
=======
    # Dominios eliminados para evitar problemas con IDs inválidos

>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    piezas_pendientes = fields.Float(
        string="Piezas Pendientes",
        tracking=True,
    )

<<<<<<< HEAD
    # ==============================================================================================
    #                               LOGICA DE SUBTAREAS PONDERADAS
    # ==============================================================================================
    # Esta sección contiene la lógica exclusiva para el manejo de "Progreso Ponderado".
    # Permite que una tarea padre calcule su avance basado en el peso (%) de sus subtareas
    # y unidades directas, en lugar de una simple suma de unidades.
    # ==============================================================================================

    # --- CAMPOS DE CONFIGURACIÓN Y ESTADO ---

    use_weighted_progress = fields.Boolean(
        string="Progreso ponderado",
        help="Si se activa, el progreso de esta tarea se calculará como la suma ponderada del progreso de sus subtareas.",
        default=False,
    )
    subtask_weight = fields.Float(
        string="(%)",
        help="Porcentaje de impacto que tiene esta subtarea sobre el progreso de la tarea padre. (0-100)",
        default=0.0,
    )
    last_update_date = fields.Datetime(
        related="last_d_update.write_date", string="Modificado por ult. vez"
    )

    quant_progress = fields.Float(
        string="Piezas/Servicio",
        compute="_units",
        store=True,
        help="Cantidad de unidades/servicios completados. Se calcula sumando los avances reportados o el progreso ponderado de subtareas."
    )
    progress = fields.Integer(
        compute="_progress",
        string="Progreso",
        store=True,
        help="Porcentaje de progreso de la tarea (0-100). Se calcula en base a quant_progress y total_pieces, o como suma ponderada de subtareas."
    )
    progress_percentage = fields.Float(
        compute="_progress_percentage",
        string="Progreso porcentual",
        store=False,
        help="Versión decimal del progreso (0.0-1.0) para cálculos internos."
    )

    is_complete = fields.Boolean(
        string="Complete", compute="_is_complete", default=False, store=False
    )

    producto_relacionado = fields.Many2one(
        'product.product',
        string="Producto Relacionado A la Tarea",
        ondelete='set null',
        help="Producto asociado a esta tarea."
    )

    # ==============================================================================================
    #                   AVANCES DE SUBTAREAS (visibles desde la tarea padre)
    # ==============================================================================================
    child_sub_update_ids = fields.Many2many(
        comodel_name='project.sub.update',
        compute='_compute_child_sub_update_ids',
        string='Avances de Subtareas',
        store=False,
        help='Todos los avances registrados en las subtareas directas de esta tarea.'
    )

    @api.depends('child_ids', 'child_ids.sub_update_ids')
    def _compute_child_sub_update_ids(self):
        for task in self:
            if not task.id or isinstance(task.id, models.NewId):
                task.child_sub_update_ids = self.env['project.sub.update']
                continue
            # Recolectar todos los avances de las subtareas directas
            child_task_ids = task.child_ids.ids
            if child_task_ids:
                avances = self.env['project.sub.update'].search([
                    ('task_id', 'in', child_task_ids)
                ], order='date desc, id desc')
                task.child_sub_update_ids = avances
            else:
                task.child_sub_update_ids = self.env['project.sub.update']

    # --- MÉTODOS DE CÁLCULO Y LÓGICA ---
    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress",
        "project_id.update_ids",
        "use_weighted_progress",
        "total_pieces",
        "child_ids.subtask_weight",
        "state"
    )
    def _units(self):
        # Optimization: Fetch sum of unit_progress for all tasks at once
        domain = [("task_id", "in", self.ids)]
        data = self.env["project.sub.update"].read_group(
            domain, ["task_id", "unit_progress"], ["task_id"]
        )
        progress_map = {item["task_id"][0]                        : item["unit_progress"] for item in data}

        for u in self:
            if not u.id:
                continue

            # CASO 1: Tarea Padre Ponderada (Calcula en base a hijos)
            if u.use_weighted_progress:
                # ESTRATEGIA MIXTA:
                # 1. Sumar contribución de subtareas
                weighted_pct = 0.0
                for child in u.child_ids:
                    current_sub_progress = child.progress or 0
                    if current_sub_progress > 0:
                        weighted_pct += (current_sub_progress /
                                         100.0) * child.subtask_weight

                # 2. Sumar avance DIRECTO en la tarea padre
                direct_progress_units = progress_map.get(u.id, 0.0)

                # Calcular cuánto representa ese avance directo del total de piezas
                if u.total_pieces > 0:
                    direct_contribution_pct = (
                        direct_progress_units / u.total_pieces) * 100.0
                    weighted_pct += direct_contribution_pct

                # Capamos al 100%
                weighted_pct = min(100.0, weighted_pct)
                u.quant_progress = (weighted_pct / 100.0) * u.total_pieces

                # Consistencia: Solo si el padre está Hecho, asumimos 100% global
                if u.state == '1_done':
                    u.quant_progress = u.total_pieces

            # CASO 2: Subtarea / Tarea Normal (Calcula sumando sus avances)
            else:
                u.quant_progress = progress_map.get(u.id, 0.0)

    @api.depends(
        "sub_update_ids",
        "sub_update_ids.unit_progress",
        "project_id.update_ids",
        "total_pieces",
        "use_weighted_progress",
        "child_ids.subtask_weight",
        "child_ids.state",
        "state",
    )
    def _progress(self):
        for u in self:
            progress = 0.0

            if u.use_weighted_progress:
                total_weighted_progress = 0.0

                # 1. Contribución de Hijos
                for child in u.child_ids:
                    # Use quant_progress instead of progress to avoid circular dependency
                    if child.total_pieces and child.total_pieces > 0:
                        current_sub_progress = (
                            child.quant_progress / child.total_pieces) * 100
                    else:
                        current_sub_progress = 0

                    if current_sub_progress > 0:
                        total_weighted_progress += (current_sub_progress /
                                                    100.0) * child.subtask_weight

                # 2. Contribución Directa
                direct_progress_units = sum(
                    u.sub_update_ids.mapped("unit_progress")
                )

                if u.total_pieces > 0:
                    direct_pct_contribution = (
                        direct_progress_units / u.total_pieces) * 100.0
                    total_weighted_progress += direct_pct_contribution

                if total_weighted_progress > 99.9:
                    progress = 100.0
                else:
                    progress = total_weighted_progress

            # PRIORIDAD 2: Cálculo Dinámico si es SUBTAREA PONDERADA
            elif u.parent_id and u.parent_id.use_weighted_progress and u.subtask_weight > 0:
                # La meta es el 100% de las piezas del padre.
                # El peso solo se usa para sumar al progreso del padre, no para limitar las unidades de la subtarea.
                denominator = u.parent_id.total_pieces

                # Evitar división por cero
                if denominator > 0:
                    progress = (u.quant_progress / denominator) * 100
                else:
                    progress = 0.0

            # PRIORIDAD 3: Cálculo estándar por piezas (Tareas normales o Padres no ponderados)
            elif u.total_pieces and u.total_pieces > 0:
                progress = (u.quant_progress / u.total_pieces) * 100

            u.progress = min(100, int(round(progress)))
            # u.progress_percentage = u.progress / 100.0

    @api.depends(
        "progress"
    )
    def _progress_percentage(self):
        for u in self:
            if not u.id:
                continue
            u.progress_percentage = u.progress / 100

    # Este estaba entre medio, pero lo incluyo aqui por ser dependencia de unit_progress
    @api.depends(
        "sale_line_id.price_subtotal"
    )
    def _subtotal(self):
        for u in self:
            if not u.id:
                continue
            u.price_subtotal = u.sale_line_id.price_subtotal or 0.0

    @api.depends("sub_update_ids", "sub_update_ids.unit_progress", "progress", "quant_progress", "total_pieces", "use_weighted_progress")
    def _is_complete(self):
        for task in self:
            task.is_complete = task._check_is_complete_value()

    def _check_is_complete_value(self):
        """
        Calcula si la tarea se considera completa basándose en el progreso.
        Retorna True/False sin modificar el estado.
        """
        self.ensure_one()
        if not self.is_control_obra:
            return False

        if self.approval_state in ["draft", "to_approve", "rejected"]:
            return False

        target_value = self.total_pieces

        # Ajustar la meta si es subtarea ponderada (Usar total del Padre)
        if self.parent_id and self.parent_id.use_weighted_progress and self.subtask_weight > 0:
            target_value = self.parent_id.total_pieces

        current_value = self.quant_progress

        if self.use_weighted_progress:
            target_value = 100.0
            current_value = float(self.progress)

        if target_value == 0:
            return False  # Evitar completado automático en tareas sin meta

        comparison = float_compare(
            current_value, target_value, precision_digits=2)

        return comparison >= 0

    def _update_completion_state_side_effects(self):
        """
        Método explícito para actualizar estado y etapa cuando cambia el progreso.
        Debe llamarse desde write() o create().
        """
        for task in self:
            if not task.is_control_obra:
                continue

            # Si la tarea NO debe procesarse (borradores, etc), saltar
            if task.approval_state in ["draft", "to_approve", "rejected"]:
                continue

            is_done = task._check_is_complete_value()

            # Lógica de transición de estados
            if is_done:
                # Solo si no está ya en done
                if task.state != '1_done':
                    vals = {
                        "state": "1_done",
                        "is_complete": True
                    }
                    stage_done = self.env.ref(
                        "project_modificaciones.project_task_type_obra_done", raise_if_not_found=False
                    )
                    if stage_done and task.stage_id != stage_done:
                        vals["stage_id"] = stage_done.id

                    task.write(vals)

            else:
                # Si NO está completa, pero estaba en done, o necesita moverse
                current_value = task.quant_progress
                if task.use_weighted_progress:
                    current_value = float(task.progress)

                # Caso: En progreso
                if current_value > 0:
                    if task.approval_state == "approved":
                        # Verificar si necesitamos moverla a "En Progreso"
                        needs_update = False
                        vals = {}

                        stage_pending = self.env.ref(
                            "project_modificaciones.project_task_type_obra_pending", raise_if_not_found=False)
                        stage_done = self.env.ref(
                            "project_modificaciones.project_task_type_obra_done", raise_if_not_found=False)
                        stage_progress = self.env.ref(
                            "project_modificaciones.project_task_type_obra_progress", raise_if_not_found=False)

                        # Si está en Pendiente o Done, mover a Progress
                        if task.stage_id in [stage_pending, stage_done] or not task.stage_id:
                            if stage_progress:
                                vals["stage_id"] = stage_progress.id
                            vals["state"] = "01_in_progress"
                            vals["is_complete"] = False
                            needs_update = True

                        # Si está manualmente marcada como done pero bajó el progreso
                        elif task.state == '1_done':
                            vals["state"] = "01_in_progress"
                            vals["is_complete"] = False
                            needs_update = True

                        if needs_update:
                            task.write(vals)

                # Caso: Sin progreso (o 0)
                else:
                    if task.approval_state == "approved":
                        needs_update = False
                        vals = {}

                        stage_progress = self.env.ref(
                            "project_modificaciones.project_task_type_obra_progress", raise_if_not_found=False)
                        stage_done = self.env.ref(
                            "project_modificaciones.project_task_type_obra_done", raise_if_not_found=False)
                        stage_pending = self.env.ref(
                            "project_modificaciones.project_task_type_obra_pending", raise_if_not_found=False)

                        if task.stage_id in [stage_progress, stage_done]:
                            if stage_pending:
                                vals["stage_id"] = stage_pending.id
                            vals["state"] = "04_waiting_normal"
                            vals["is_complete"] = False
                            needs_update = True

                        elif task.state == '1_done':
                            vals["state"] = "04_waiting_normal"
                            vals["is_complete"] = False
                            needs_update = True

                        if needs_update:
                            task.write(vals)
            # Si es una subtarea, verificar si el padre debe actualizarse
            if task.parent_id:
                task.parent_id._update_completion_state_side_effects()

    @api.model
    def update_task_status(self):
        tasks = self.env["project.task"].search(
            [("sale_order_id", "!=", False)])
        # Trigger side effects manually for cron/server actions
        tasks._update_completion_state_side_effects()

    # ==============================================================================================
    #                            FIN LOGICA DE SUBTAREAS PONDERADAS
    # ==============================================================================================

    # -------------------------------------------------------------------------
    # MÉTODOS
=======
    producto_relacionado = fields.Many2one(
        'product.product',
        string="Producto Relacionado A la Tarea",
    )

    # -------------------------------------------------------------------------
    # MÉTODOS TRAIDOS TAL CUAL DE INHERIT_PROJECT_TASK.PY
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    # -------------------------------------------------------------------------

    @api.depends("sale_line_id.qty_invoiced")
    def _invoiced(self):
        for u in self:
            u.invoiced = u.qty_invoiced * u.price_unit

<<<<<<< HEAD
    @api.model
    def _check_to_recompute(self):
        return [id]

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
=======
    @api.depends("sub_update_ids")
    def _d_update(self):
        for task in self:
            updates = task.sub_update_ids.sorted(
                key=lambda update: update.write_date or update.create_date or fields.Datetime.now(),
                reverse=True,
            )
            task.sub_d_update = updates[:1]

    @api.model
    def _check_to_recompute(self):
        """Stub auxiliar. Devuelve los IDs del recordset actual para recompute externo."""
        return self.ids

    @api.depends("sub_update_ids")
    def _last_update(self):
        for task in self:
            if not task.id:
                continue
            task.sub_update = task.sub_update_ids.sorted(
                key=lambda update: update.write_date or update.create_date or fields.Datetime.now(),
                reverse=True,
            )[:1]

    @api.depends(
        "sub_update_ids",
        "sub_update_ids.unit_progress",
        "sub_update_ids.avances_state",
        "project_id.update_ids"
    )
    def _units(self):
        for u in self:
            # Verifica si el registro está siendo creado (i.e., no tiene ID aún)
            if not u.id:
                continue

            # Sincronización Maestra: Sumamos todos los avances vinculados (sin filtrar por estado)
            u.quant_progress = sum(u.sub_update_ids.mapped("unit_progress"))

            # Empujar el cambio directamente a la línea de venta para asegurar consistencia
            if u.sale_line_id:
                u.sale_line_id.qty_delivered = u.quant_progress

    def _get_progress_denominator(self):
        """Devuelve el total esperado para calcular el progreso de la tarea.

        - En venta, se usa total_pieces.
        - En pendientes sin venta, se usa piezas_pendientes.
        """
        self.ensure_one()
        if self.sale_order_id and self.total_pieces:
            return self.total_pieces
        return self.piezas_pendientes or self.total_pieces or 0.0

    @api.depends(
        "sub_update_ids",
        "sub_update_ids.unit_progress",
        "project_id.update_ids",
        "quant_progress",
        "total_pieces",
        "piezas_pendientes",
        "sale_order_id",
    )
    def _progress(self):
        for u in self:
            progress = 0.0
            denominator = u._get_progress_denominator()
            if denominator > 0:
                progress = (u.quant_progress / denominator) * 100

            # Mantiene el valor entero que ya usa la UI, pero con base correcta.
            u.progress = min(100, int(progress))

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "project_id.update_ids"
    )
    def _progress_percentage(self):
        for task in self:
            task.progress_percentage = (task.progress or 0) / 100

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "project_id.update_ids"
    )
    def _subtotal(self):
        for task in self:
            task.price_subtotal = task.sale_line_id.price_subtotal or 0.0

    @api.depends("sub_update_ids", "sub_update_ids.unit_progress")
    def _is_complete(self):
        self._update_completion_state()

    def _update_completion_state(self):
        for task in self:
            # Solo aplicar validación estricta para tareas de CONTROL DE OBRA
            if not task.is_control_obra:
                continue

            denominator = task._get_progress_denominator()
            if denominator <= 0:
                continue

            progress_reached = (task.progress or 0) >= 100
            quantity_reached = task.quant_progress >= denominator

            if progress_reached or quantity_reached:
                task.is_complete = True
                task.state = "1_done"
                task.stage_id = self.env.ref(
                    "project_modificaciones.project_task_type_obra_done", raise_if_not_found=False
                )
            elif task.quant_progress > 0:
                task.is_complete = False
                # Si baja de 100%, reabrir y mover a "En Progreso".
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
                    or task.state == "1_done"
                ):
                    task.stage_id = self.env.ref(
                        "project_modificaciones.project_task_type_obra_progress",
                        raise_if_not_found=False,
                    )
                task.state = "01_in_progress"
            else:
                task.is_complete = False
                # Si regresa a 0, mover a pendientes solo si estaba en progreso o listo
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
                    task.state = (
                        "04_waiting_normal"  # Solo control obra usa este estado
                    )

    @api.model
    def update_task_status(self):
        tasks = self.env["project.task"].search(
            [("sale_order_id", "!=", False)])
        tasks._update_completion_state()

    """ REVISAR
    @api.constrains('sub_update_ids')
    def _check_unique_items(self):
        for record in self:
            item_ids = record.item_ids.mapped('update_id')
            if len(item_ids) != len(set(item_ids)):
                raise ValidationError('No se pueden agregar ítems duplicados.')
    """

    # -------------------------------------------------------------------------
    # MÉTODO AUXILIAR: Actualiza el JSON de distribución analítica
    # -------------------------------------------------------------------------
    def _get_updated_analytic_distribution(self, distribution, new_account_id, old_account_id=False):
        """
        Recibe la distribución actual (Dict) y reemplaza la cuenta analítica vieja por la nueva.
        Mantiene el porcentaje original.
        """
        if not new_account_id:
            return distribution or {}

        # Asegurar que distribution sea un diccionario modificable
        new_dist = dict(distribution or {})

        # En Odoo 17 las claves del JSON analítico son Strings
        str_new_id = str(new_account_id)
        str_old_id = str(old_account_id) if old_account_id else False

        # 1. Si existía la cuenta vieja, tomamos su porcentaje y la borramos
        percentage = 100.0
        if str_old_id and str_old_id in new_dist:
            percentage = new_dist.pop(str_old_id)

        # 2. Asignamos la nueva cuenta
        # Si ya existe la nueva (caso raro), sumamos el porcentaje para no duplicar claves
        new_dist[str_new_id] = new_dist.get(str_new_id, 0.0) + percentage

        return new_dist

    def merge_into_task(self, target_task, pending_service=False, pending_service_line=False):
        self.ensure_one()
        if not target_task or self == target_task:
            return {
                'target_task': target_task,
                'moved': {},
            }

        new_project = target_task.project_id
        new_analytic = target_task.analytic_account_id or new_project.analytic_account_id
        old_analytic = self.analytic_account_id or self.project_id.analytic_account_id
        moved = {
            'avances': len(self.sub_update_ids),
            'gastos': len(self.expense_ids.filtered(lambda e: e.state not in ['done', 'refused'])) if 'expense_ids' in self._fields else 0,
            'compras': 0,
            'horas': 0,
            'mov_almacen': len(self.stock_move_ids) if 'stock_move_ids' in self._fields else 0,
            'requisiciones': len(self.requisition_ids.filtered(lambda r: r.state != 'cancel')) if 'requisition_ids' in self._fields else 0,
            'regularizaciones': 0,
            'compensaciones': 0,
        }

        if not new_project:
            raise ValidationError(
                _("La tarea destino '%s' no tiene proyecto asignado.") % target_task.display_name
            )

        # 1. Avances y project.update por fecha
        if self.sub_update_ids:
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            avances_by_date = {}
            for avance in self.sub_update_ids:
                avance_date = avance.date or fields.Date.today()
                if avance_date not in avances_by_date:
                    avances_by_date[avance_date] = self.env['project.sub.update']
                avances_by_date[avance_date] |= avance

            for p_date, avances in avances_by_date.items():
                existing_update = self.env['project.update'].search([
                    ('project_id', '=', new_project.id),
<<<<<<< HEAD
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
                # Removed 'done' from filter to handle locks via code
                lambda e: e.state not in ['refused'])

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

        # self.env['project.sub.update'].invalidate_model()
        # self.invalidate_recordset()

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

        # self.sudo().write({
        #     'progress': new_progress,
        #     'progress_percentage': new_pct
        # })

        if self.sale_line_id:
            # self.sale_line_id.sudo().write(
            #    {'qty_delivered': current_quant})
            pass

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
=======
                    ('date', '=', p_date),
                ], limit=1)

                if not existing_update:
                    update_name = avances[0].update_id.name if avances and avances[0].update_id else _('Actualización Transferida')
                    try:
                        existing_update = self.env['project.update'].create({
                            'project_id': new_project.id,
                            'name': update_name,
                            'date': p_date,
                            'user_id': self.env.user.id,
                            'status': 'on_track',
                        })
                    except Exception as exc:
                        _logger.warning("No se pudo crear project.update destino durante fusión: %s", exc)
                        existing_update = False

                vals_avance = {
                    'task_id': target_task.id,
                    'project_id': new_project.id,
                    'update_id': existing_update.id if existing_update else False,
                }
                if pending_service:
                    vals_avance['pending_service_id'] = pending_service.id
                if pending_service_line:
                    vals_avance['pending_service_line_id'] = pending_service_line.id
                avances.write(vals_avance)

        # 2. Gastos
        if 'expense_ids' in self._fields:
            all_expenses = self.expense_ids.filtered(lambda e: e.state not in ['done', 'refused'])
            for expense in all_expenses.sudo():
                vals_expense = {
                    'task_id': target_task.id,
                    'project_id': new_project.id,
                }
                if new_analytic and 'analytic_distribution' in expense._fields:
                    vals_expense['analytic_distribution'] = self._get_updated_analytic_distribution(
                        expense.analytic_distribution, new_analytic.id, old_analytic.id if old_analytic else False
                    )
                expense.write(vals_expense)

        # 3. Compras, albaranes y movimientos
        purchase_orders = self.env['purchase.order'].search([
            ('task_order_id', '=', self.id),
            ('state', '!=', 'cancel'),
        ])
        if purchase_orders:
            moved['compras'] += len(purchase_orders)
            purchase_orders.write({
                'task_order_id': target_task.id,
                'project_id': new_project.id,
            })
            for line in purchase_orders.mapped('order_line').filtered(lambda l: l.state != 'cancel'):
                vals_line = {
                    'task_id': target_task.id,
                    'project_id': new_project.id,
                }
                if new_analytic and 'analytic_distribution' in line._fields:
                    vals_line['analytic_distribution'] = self._get_updated_analytic_distribution(
                        line.analytic_distribution, new_analytic.id, old_analytic.id if old_analytic else False
                    )
                line.write(vals_line)
            pickings = purchase_orders.mapped('picking_ids').filtered(lambda p: p.state != 'cancel')
            if pickings:
                pickings.write({'task_id': target_task.id, 'project_id': new_project.id})
                pickings.mapped('move_ids').filtered(lambda m: m.state != 'cancel').write({
                    'task_id': target_task.id,
                    'project_id': new_project.id,
                })

        if 'purchase_line_ids' in self._fields:
            loose_lines = self.purchase_line_ids.filtered(
                lambda l: l.state not in ['cancel', 'done'] and l.order_id not in purchase_orders
            )
            for line in loose_lines:
                vals_line = {
                    'task_id': target_task.id,
                    'project_id': new_project.id,
                }
                if new_analytic and 'analytic_distribution' in line._fields:
                    vals_line['analytic_distribution'] = self._get_updated_analytic_distribution(
                        line.analytic_distribution, new_analytic.id, old_analytic.id if old_analytic else False
                    )
                line.write(vals_line)

        # 4. Timesheets
        if 'timesheet_ids' in self._fields:
            timesheets_model = self.env['account.analytic.line']
            if 'timesheet_invoice_id' in timesheets_model._fields:
                timesheets = self.timesheet_ids.filtered(lambda t: not t.timesheet_invoice_id)
            else:
                timesheets = self.timesheet_ids
            if timesheets:
                moved['horas'] = len(timesheets)
                ts_vals = {
                    'task_id': target_task.id,
                    'project_id': new_project.id,
                }
                if target_task.sale_line_id and 'so_line' in timesheets._fields:
                    ts_vals['so_line'] = target_task.sale_line_id.id
                timesheets.write(ts_vals)

        # 5. Stock moves directos
        if 'stock_move_ids' in self._fields and self.stock_move_ids:
            self.stock_move_ids.write({
                'task_id': target_task.id,
                'project_id': new_project.id,
            })

        # 6. Requisiciones
        if 'requisition_ids' in self._fields:
            for req in self.requisition_ids.filtered(lambda r: r.state != 'cancel'):
                req_vals = {}
                if 'task_id' in req._fields:
                    req_vals['task_id'] = target_task.id
                if 'project_id' in req._fields:
                    req_vals['project_id'] = new_project.id
                if 'analytic_distribution' in req._fields and new_analytic:
                    req_vals['analytic_distribution'] = self._get_updated_analytic_distribution(
                        getattr(req, 'analytic_distribution', {}), new_analytic.id, old_analytic.id if old_analytic else False
                    )
                if req_vals:
                    req.write(req_vals)
                if hasattr(req, 'requisition_order_ids') and req.requisition_order_ids:
                    line_vals = {}
                    if 'project_id' in self.env['requisition.order']._fields:
                        line_vals['project_id'] = new_project.id
                    if line_vals:
                        req.requisition_order_ids.write(line_vals)

        # 7. Otros modelos auxiliares
        attendance_model = self.env.get('attendance.regularization')
        if attendance_model is not None and 'task_id' in attendance_model._fields:
            attendance_recs = attendance_model.search([('task_id', '=', self.id)])
            if attendance_recs:
                moved['regularizaciones'] = len(attendance_recs)
                vals_att = {'task_id': target_task.id}
                if 'project_id' in attendance_model._fields:
                    vals_att['project_id'] = new_project.id
                attendance_recs.write(vals_att)

        comp_line_model = self.env.get('compensation.line')
        if comp_line_model is not None and 'task_id' in comp_line_model._fields:
            comp_lines = comp_line_model.search([('task_id', '=', self.id)])
            if comp_lines:
                moved['compensaciones'] = len(comp_lines)
                vals_comp = {'task_id': target_task.id}
                if 'project_id' in comp_line_model._fields:
                    vals_comp['project_id'] = new_project.id
                comp_lines.write(vals_comp)

        return {
            'target_task': target_task,
            'moved': moved,
        }

    # -------------------------------------------------------------------------
    # MÉTODO WRITE: Lógica principal de cambio de proyecto
    # -------------------------------------------------------------------------
    def write(self, vals):
        # 1. Capturar estado previo
        old_state = {
            task.id: {
                'project_id': task.project_id,
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
                'analytic_account_id': task.analytic_account_id or task.project_id.analytic_account_id,
                'sale_order_id': task.sale_order_id
            } for task in self
        }

<<<<<<< HEAD
        res = super(Task, self).write(vals)

=======
        # 2. Ejecutar write estándar
        res = super(Task, self).write(vals)

        # 3. Detectar si el cambio incluyó 'project_id'
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        if "project_id" in vals:
            self._compute_is_control_obra()
            new_project_id = vals.get('project_id')
            new_project = self.env['project.project'].browse(
                new_project_id) if new_project_id else self.env['project.project']

            for task in self:
                prev_data = old_state.get(task.id)
<<<<<<< HEAD
                if prev_data:
                    task._handle_project_change(prev_data, new_project)

        # Trigger completion logic if progress related fields changed
        if any(f in vals for f in ['quant_progress', 'progress', 'total_pieces', 'subtask_weight', 'use_weighted_progress']):
            # Avoid recursion: if we are already writing state/stage, don't re-trigger unless necessary
            # But _update_completion_state_side_effects checks current state before writing.

            # IMPORTANT: Since store=True fields like quant_progress might be updated by Odoo BEFORE calling write (in case of recompute)
            # or implicitly.
            # Actually, when recompute happens, Odoo calls write(['quant_progress': X]).
            # So this hook captures recomputes too!
            self._update_completion_state_side_effects()

        return res

    def _compute_updates_count(self):
        # Optimize by fetching all counts in one go for simple cases
        # For weighted progress, logic is complex (children + self), so might need custom logic

        # 1. Simple count for all tasks
        domain_simple = [('task_id', 'in', self.ids)]
        data_simple = self.env['project.sub.update'].read_group(
            domain_simple, ['task_id'], ['task_id'])
        count_map = {item['task_id'][0]: item['task_id_count']
                     for item in data_simple}

        for task in self:
            count = 0
            if task.use_weighted_progress and task.child_ids:
                # Complicated case: recursive or children check.
                # If we want to be 100% efficient we need to fetch for all children too.
                # For now, let's keep search_count but only for this specific complex case.
                # Or better: pre-load child IDs?
                # Given strictness of "optimize", let's use search_count but on the specific ID set.
                ids_to_check = task.child_ids.ids + [task.id]
                count = self.env['project.sub.update'].search_count([
                    ('task_id', 'in', ids_to_check)
                ])
            else:
                count = count_map.get(task.id, 0)
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
=======
                old_project = prev_data['project_id']
                old_analytic = prev_data['analytic_account_id']
                sale_order = prev_data['sale_order_id']

                # Solo procesamos si hay un cambio real de proyecto
                if old_project and new_project and old_project != new_project:

                    # === A) ACTUALIZAR CUENTA ANALÍTICA TAREA ===
                    new_analytic = new_project.analytic_account_id
                    if new_analytic and task.analytic_account_id != new_analytic:
                        task.write({'analytic_account_id': new_analytic.id})

                    # === B) MOVER AVANCES CON LOGICA DE PROJECT.UPDATE ===
                    if task.sub_update_ids:
                        # 0. Capturar los updates de origen para verificar limpieza posterior
                        source_updates = task.sub_update_ids.mapped(
                            'update_id')

                        # 1. Agrupar avances por fecha para procesar en lote
                        avances_by_date = {}
                        for avance in task.sub_update_ids:
                            # Usamos la fecha del avance o fallback a hoy
                            avance_date = avance.date or fields.Date.today()
                            if avance_date not in avances_by_date:
                                avances_by_date[avance_date] = self.env['project.sub.update']
                            avances_by_date[avance_date] |= avance

                        # 2. Iterar por cada grupo de fecha
                        for p_date, avances in avances_by_date.items():
                            # Buscar una actualización existente en el NUEVO PROYECTO con la misma fecha
                            # Asumimos que la comparación es por fecha (date)
                            existing_update = self.env['project.update'].search([
                                ('project_id', '=', new_project.id),
                                ('date', '=', p_date)
                            ], limit=1)

                            if not existing_update:
                                # Si no existe, la CREAMOS
                                # Intentamos preservar el nombre de la actualización original si es posible
                                original_update_name = _(
                                    'Actualización Transferida')
                                # Tomamos el nombre del update del primer avance si existe
                                if avances and (valid_update_id := avances[0].update_id):
                                    original_update_name = valid_update_id.name

                                try:
                                    existing_update = self.env['project.update'].create({
                                        'project_id': new_project.id,
                                        'name': original_update_name,
                                        'date': p_date,
                                        'user_id': self.env.user.id,
                                        # Status por defecto (ej. on_track) suele ser requerido o tener default
                                        'status': 'on_track'
                                    })
                                    _logger.info(
                                        "Creado nuevo Project Update %s en proyecto %s para fecha %s",
                                        existing_update.name, new_project.name, p_date
                                    )
                                except Exception as e:
                                    _logger.warning(
                                        "No se pudo crear project.update automático: %s. Los avances se moverán sin update_id.", str(e))
                                    existing_update = False

                            # 3. Mover los avances y asignarlos al update encontrado/creado
                            vals_avance = {'project_id': new_project.id}
                            if existing_update:
                                vals_avance['update_id'] = existing_update.id
                            else:
                                # CRÍTICO: Si no se pudo crear el update nuevo, DESVINCULAR del viejo
                                # para evitar que apunten a un update de otro proyecto.
                                vals_avance['update_id'] = False

                            avances.write(vals_avance)

                        # 4. Limpieza: Eliminar updates de origen que quedaron vacíos
                        for old_update in source_updates:
                            # Contamos si quedan avances vinculados
                            # Nota: update_id es el campo Many2one en project.sub.update hacia project.update
                            # Asumimos que existe un One2many en project.update o buscamos inversamente
                            # Normalmente no hay One2many por defecto de sub.update en project.update salvo personalizacion
                            # Buscamos count directo
                            count_remaining = self.env['project.sub.update'].search_count(
                                [('update_id', '=', old_update.id)])
                            if count_remaining == 0:
                                _logger.info(
                                    "Eliminando Project Update vacío tras mudanza: %s (ID: %s)", old_update.name, old_update.id)
                                old_update.sudo().unlink()

                    # === C) MOVER SUBTAREAS ===
                    child_tasks = self.search(
                        [('parent_id', '=', task.id), ('project_id', '=', old_project.id)])
                    if child_tasks:
                        child_tasks.write({'project_id': new_project.id})

                    # === D) ACTUALIZAR GASTOS (HR.EXPENSE) ===
                    # Verificamos si existe el campo y filtramos
                    if 'expense_ids' in self.env['project.task']._fields:
                        # 1. Separamos gastos: "Libres" vs "Bloqueados" (En reporte aprobado/posteado/pagado)
                        all_expenses = task.expense_ids.filtered(
                            lambda e: e.state not in ['done', 'refused'])

                        expenses_free = all_expenses.filtered(
                            lambda e: not e.sheet_id or e.sheet_id.state in ['draft', 'submit'])
                        expenses_locked = all_expenses - expenses_free

                        # CASO 1: Gastos Libres -> Usamos write estandard (con sudo)
                        if expenses_free:
                            vals_expense = {'project_id': new_project.id}
                            if new_analytic:
                                # Hay que iterar porque cada uno tiene su propia distribución
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

                        # CASO 2: Gastos Bloqueados -> Actualizamos Proyecto Y Analítica vía SQL
                        # Nota de seguridad: usamos parámetros bind (%s) en lugar de
                        # interpolación de strings para evitar inyección SQL.
                        if expenses_locked:
                            _logger.info(
                                "Forzando actualización de proyecto/analítica en %s gastos bloqueados", len(expenses_locked))

                            for exp in expenses_locked:
                                # Si hay nueva analítica, calculamos el JSON y lo actualizamos
                                if new_analytic:
                                    new_dist = self._get_updated_analytic_distribution(
                                        exp.analytic_distribution, new_analytic.id, old_analytic.id
                                    )
                                    json_dist = json.dumps(new_dist)
                                    # Usamos parámetros bind para project_id Y analytic_distribution
                                    self.env.cr.execute(
                                        """
                                        UPDATE hr_expense
                                        SET project_id = %s,
                                            analytic_distribution = %s::jsonb
                                        WHERE id = %s
                                        """,
                                        (new_project.id, json_dist, exp.id)
                                    )
                                else:
                                    self.env.cr.execute(
                                        """
                                        UPDATE hr_expense
                                        SET project_id = %s
                                        WHERE id = %s
                                        """,
                                        (new_project.id, exp.id)
                                    )

                            # Invalidar caché
                            expenses_locked.invalidate_recordset(
                                ['project_id', 'analytic_distribution'])

                    # === E) ACTUALIZAR COMPRAS (PURCHASE.ORDER) ===
                    # 1. Buscar Órdenes de Compra vinculadas a esta tarea como cabecera
                    purchase_orders = self.env['purchase.order'].search([
                        ('task_order_id', '=', task.id),
                        ('state', '!=', 'cancel')
                    ])

                    if purchase_orders:
                        # Actualizar proyecto en cabecera
                        purchase_orders.write({'project_id': new_project.id})

                        # A) LÍNEAS DE COMPRA (Actualizar Proyecto y Analítica)
                        lines_to_update = purchase_orders.mapped('order_line').filtered(
                            lambda l: l.state != 'cancel'
                        )
                        if lines_to_update:
                            vals_line = {
                                'project_id': new_project.id,
                                # Asegurar que NO se pierda la tarea (Corrección solicitada)
                                'task_id': task.id
                            }
                            # Si hay analítica, forzamos actualización en TODAS las líneas de la orden
                            if new_analytic:
                                # Iteramos por si tienen distribuciones mixtas, aunque es pesado es seguro
                                for line in lines_to_update:
                                    _logger.debug("ANALYTIC: Old=%s, New=%s, Dist=%s",
                                                  old_analytic.id, new_analytic.id, line.analytic_distribution)
                                    dist = self._get_updated_analytic_distribution(
                                        line.analytic_distribution, new_analytic.id, old_analytic.id)
                                    _logger.debug(
                                        "ANALYTIC RESULT: %s", dist)

                                    line_vals = vals_line.copy()
                                    line_vals['analytic_distribution'] = dist
                                    line.write(line_vals)
                            else:
                                lines_to_update.write(vals_line)

                        # B) ALBARANES (STOCK PICKING)
                        pickings = purchase_orders.mapped('picking_ids').filtered(
                            lambda p: p.state != 'cancel'
                        )
                        if pickings:
                            # Propagar TAREA también
                            pickings.write({
                                'project_id': new_project.id,
                                'task_id': task.id  # Corrección solicitada
                            })

                            # C) MOVIMIENTOS DE STOCK (STOCK MOVE)
                            moves = pickings.mapped('move_ids').filtered(
                                lambda m: m.state != 'cancel'
                            )
                            if moves:
                                moves.write({
                                    'project_id': new_project.id,
                                    'task_id': task.id
                                })

                    # 2. Actualizar Distribución Analítica en líneas sueltas (linked directly)
                    # (Esto cubre líneas que NO son de las órdenes de arriba, si hubiera)
                    if 'purchase_line_ids' in self.env['project.task']._fields:
                        # Buscamos líneas que NO fueron actualizadas arriba
                        processed_orders = purchase_orders.ids if purchase_orders else []
                        purchase_lines = task.purchase_line_ids.filtered(
                            lambda l: l.state not in ['cancel', 'done'] and l.order_id.id not in processed_orders)

                        if purchase_lines:
                            _logger.info("Actualizando %s líneas de compra sueltas para tarea %s", len(
                                purchase_lines), task.name)
                            vals_line_loose = {'project_id': new_project.id}

                            if new_analytic:
                                for line in purchase_lines:
                                    _logger.debug("ANALYTIC LOOSE: Old=%s, New=%s, Dist=%s",
                                                  old_analytic.id if old_analytic else False, new_analytic.id, line.analytic_distribution)
                                    new_dist_line = self._get_updated_analytic_distribution(
                                        line.analytic_distribution, new_analytic.id, old_analytic.id
                                    )
                                    _logger.debug(
                                        "ANALYTIC LOOSE RESULT: %s", new_dist_line)

                                    curr_vals = vals_line_loose.copy()
                                    curr_vals['analytic_distribution'] = new_dist_line
                                    line.write(curr_vals)
                            else:
                                purchase_lines.write(vals_line_loose)

                    # === F) ACTUALIZAR TIMESHEETS ===
                    if 'timesheet_ids' in self.env['project.task']._fields:
                        timesheets_model = self.env['account.analytic.line']
                        if 'timesheet_invoice_id' in timesheets_model._fields:
                            timesheets = task.timesheet_ids.filtered(
                                lambda t: not t.timesheet_invoice_id)
                        else:
                            timesheets = task.timesheet_ids

                        if timesheets:
                            ts_vals = {'project_id': new_project.id}
                            if task.sale_line_id:
                                ts_vals['so_line'] = task.sale_line_id.id
                            timesheets.write(ts_vals)

                    # === G) ACTUALIZAR MOVIMIENTOS DE ALMACÉN (STOCK.MOVE) ===
                    # El usuario solicitó explícitamente que los movimientos de almacén también se muevan.
                    if 'stock_move_ids' in self.env['project.task']._fields:
                        moves_to_update = task.stock_move_ids.filtered(
                            lambda m: m.state not in ['cancel', 'done']
                        )
                        # También podríamos incluir los 'done' si se requiere historial,
                        # pero comúnmente solo se mueven los abiertos.
                        # Si el cliente quiere TODOS (historial incluido), quitamos el filtro de state.
                        # Asumiendo "que se muevan" implica reasignación total:
                        moves_to_update = task.stock_move_ids
                        if moves_to_update:
                            moves_to_update.write(
                                {'project_id': new_project.id})

                    # === H) RECALCULAR AVANCE (CRÍTICO - FUERZA BRUTA 2.0) ===
                    # 1. Limpieza agresiva de cache
                    # Aseguar que el search() vea los cambios de proyecto
                    self.env['project.sub.update'].invalidate_model()
                    task.invalidate_recordset()  # Invalidar TODO en la tarea

                    # 2. Recalcular Unidades (Numerador)
                    task._units()
                    current_quant = task.quant_progress

                    # 3. Obtener Total (Denominador) Fresco
                    total_qty = 0.0
                    if task.sale_line_id:
                        # Leer directamente de la BD saltando caché posible
                        linea = self.env['sale.order.line'].browse(
                            task.sale_line_id.id)
                        total_qty = linea.product_uom_qty

                    # 4. Calcular Porcentajes manualmente
                    new_progress = 0
                    new_pct = 0.0

                    if total_qty > 0 and current_quant > 0:
                        new_progress_float = (current_quant / total_qty) * 100
                        new_progress = min(100, int(new_progress_float))
                        new_pct = new_progress_float / 100.0  # Usamos float preciso

                    # 5. Escribir explícitamente los valores con SUDO
                    _logger.info("FORCE UPDATE FINAL: Task %s | Quant: %s | Total: %s | Calc Progress: %s",
                                 task.name, current_quant, total_qty, new_progress)

                    task.sudo().write({
                        'progress': new_progress,
                        'progress_percentage': new_pct
                    })

                    pass

                    # === I) ACTUALIZAR REQUISICIONES (EMPLOYEE.PURCHASE.REQUISITION) ===
                    # Si existen requisiciones vinculadas, las movemos al nuevo proyecto.
                    if 'requisition_ids' in self.env['project.task']._fields:
                        requisitions_to_move = task.requisition_ids.filtered(
                            # O mover todas si se prefiere historial completo:
                            lambda r: r.state not in ['cancel']
                        )

                        for req in requisitions_to_move:
                            # 1. Cabecera (Proyecto + Analítica)
                            req_vals = {}
                            if 'project_id' in self.env['employee.purchase.requisition']._fields:
                                req_vals['project_id'] = new_project.id

                            # Si tiene campo de distribución (algunos módulos lo tienen en cabecera)
                            if 'analytic_distribution' in self.env['employee.purchase.requisition']._fields and new_analytic:
                                # Hay que ver si se puede leer el actual, asumimos que sí
                                curr_dist = req.analytic_distribution if hasattr(
                                    req, 'analytic_distribution') else {}
                                req_vals['analytic_distribution'] = self._get_updated_analytic_distribution(
                                    curr_dist, new_analytic.id, old_analytic.id
                                )

                            if req_vals:
                                req.write(req_vals)

                            # 2. Líneas (requisition.order)
                            if hasattr(req, 'requisition_order_ids') and req.requisition_order_ids:
                                # Iteramos líneas para actualizar Proyecto + Analítica
                                lines_req = req.requisition_order_ids
                                if 'project_id' in self.env['requisition.order']._fields:
                                    lines_req.write(
                                        {'project_id': new_project.id})

                                # Actualizar distribución en líneas
                                if 'analytic_distribution' in self.env['requisition.order']._fields and new_analytic:
                                    for l_req in lines_req:
                                        dist_req = self._get_updated_analytic_distribution(
                                            l_req.analytic_distribution, new_analytic.id, old_analytic.id)
                                        l_req.write(
                                            {'analytic_distribution': dist_req})

                    # === J) ACTUALIZAR HOJAS DE HORAS / REGULARIZACIONES (ATTENDANCE.REGULARIZATION) ===
                    # Buscamos registros vinculados a esta tarea.
                    # Asumimos que el modelo es 'attendance.regularization' y tiene 'task_id'.
                    attendance_model = self.env.get(
                        'attendance.regularization')
                    if attendance_model is not None and 'task_id' in attendance_model._fields:
                        attendance_recs = attendance_model.search([
                            ('task_id', '=', task.id)
                        ])
                        if attendance_recs and 'project_id' in attendance_model._fields:
                            attendance_recs.write(
                                {'project_id': new_project.id})

                    # === L) ACTUALIZAR COMPENSACIONES (COMPENSATION.REQUEST / LINE) ===
                    # Buscamos de forma segura el modelo
                    comp_line_model = self.env.get('compensation.line')
                    if comp_line_model is not None and 'task_id' in comp_line_model._fields:
                        # 1. Buscar líneas de compensación vinculadas a esta tarea
                        comp_lines = comp_line_model.search(
                            [('task_id', '=', task.id)])

                        if comp_lines:
                            # Actualizar proyecto en las líneas
                            if 'project_id' in comp_line_model._fields:
                                comp_lines.write(
                                    {'project_id': new_project.id})

                            # 2. Verificar cabeceras (request) para actualizar 'service' si unique_project es True
                            # Obtenemos las cabeceras únicas afectadas
                            comp_requests = comp_lines.mapped(
                                'compensation_id')
                            for req in comp_requests:
                                # Verificamos existencia de campos en cabecera
                                if 'unique_project' in req._fields and 'service' in req._fields:
                                    if req.unique_project:
                                        # Si el proyecto único está activo, actualizamos la cabecera también
                                        # Nota: Esto asume que TODAS las líneas pertenecían al mismo proyecto anterior.
                                        if req.service != new_project:
                                            req.write(
                                                {'service': new_project.id})

                    # === K) ACTUALIZAR SALE ORDER (Lógica "Última Tarea") ===
                    if sale_order and sale_order.project_id == old_project:
                        # Buscamos si quedan tareas (ACTIVAS o ARCHIVADAS) de esta venta en el viejo proyecto
                        # Usamos active_test=False para encontrar tareas archivadas que podrían estar causando
                        # que la venta siga vinculada al proyecto viejo (y por eso salen duplicados en el smart button).
                        tasks_remaining_all = self.with_context(active_test=False).search_count([
                            ('project_id', '=', old_project.id),
                            ('sale_order_id', '=', sale_order.id)
                        ])

                        if tasks_remaining_all == 0:
                            _logger.info(
                                "Moviendo Orden de Venta %s al proyecto %s (Limpieza completa)", sale_order.name, new_project.name)
                            sale_order.sudo().write(
                                {'project_id': new_project.id})
                        else:
                            # Si quedan tareas (quizás archivadas), las movemos también para limpiar la casa?
                            # O solo movemos la cabecera forzadamente?
                            # Estrategia: Si solo quedan archivadas, movemos la cabecera y movemos las archivadas también.

                            active_tasks = self.search_count([
                                ('project_id', '=', old_project.id),
                                ('sale_order_id', '=', sale_order.id)
                            ])

                            if active_tasks == 0 and tasks_remaining_all > 0:
                                # Significa que solo quedan "Fantasmas" (archivadas).
                                # Las movemos todas al nuevo proyecto para sanear.
                                archived_tasks = self.with_context(active_test=False).search([
                                    ('project_id', '=', old_project.id),
                                    ('sale_order_id', '=', sale_order.id)
                                ])
                                _logger.info(
                                    "Moviendo %s tareas archivadas restantes de la SO %s al nuevo proyecto",
                                    len(archived_tasks), sale_order.name
                                )
                                archived_tasks.write(
                                    {'project_id': new_project.id})

                                # Y finalmente movemos la orden
                                sale_order.sudo().write(
                                    {'project_id': new_project.id})

        return res

    """
    def _clean_invalid_references(self):
        for task in self:
            # Solo procesar tareas que tengan ID (ya guardadas)
            if not task.id:
                continue

            for field_name, field in self._fields.items():
                if field.type == "many2one" and field.store:
                    try:
                        value = getattr(task, field_name)

                        # Fix for KeyError: 30 - forcefully clear stage_id 30
                        # This ID seems to exist but causes read errors (possibly access rules or corruption)
                        if value and value.id == 30:
                            _logger.warning(
                                "🧹 FORCE CLEANING problematic reference ID 30 in tarea %s (ID: %s): campo %s",
                                task.name,
                                task.id,
                                field_name,
                            )
                            task.with_context(skip_invalid_ref_check=True).write(
                                {field_name: False}
                            )
                            continue

                        # Verificar si el valor existe pero el registro relacionado no
                        if value and not value.exists():
                            _logger.warning(
                                "🧹 Limpiando referencia inválida en tarea %s (ID: %s): campo %s = %s",
                                task.name,
                                task.id,
                                field_name,
                                value.id if value else "False",
                            )
                            # Escribir solo si realmente cambiamos algo
                            task.with_context(skip_invalid_ref_check=True).write(
                                {field_name: False}
                            )
                    except Exception as e:
                        # Silenciar errores de acceso, pero loguearlos para debugging
                        _logger.debug(
                            "Error verificando campo %s en tarea %s: %s",
                            field_name,
                            task.id,
                            str(e),
                        )
    """

    def action_view_avances(self):
        return {
            "name": _("Avances de la Tarea"),
            "type": "ir.actions.act_window",
            "res_model": "project.sub.update",  # Referencia actualizada
            "view_mode": "list,form",
            "domain": [("task_id", "=", self.id)],
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            "context": {
                "default_task_id": self.id,
                "default_project_id": self.project_id.id,
                "create": True,
<<<<<<< HEAD
                "delete": True,
=======
                "delete": False,
                "soft_reload": True,
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            },
            "flags": {"creatable": True},
            "target": "current",
        }

<<<<<<< HEAD
    def _compute_counts(self):
        for task in self:
            task.expense_count = len(task.expense_ids)
=======
    # ========== MÉTODOS DE ANALYTICS_EXTRA (mod_task.py) ==========
    def _compute_counts(self):
        for task in self:
            task.expense_count = len(task.expense_ids)
            # Contar las órdenes de compra únicas a través de las líneas
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            task.purchase_count = len(
                task.purchase_line_ids.mapped("order_id"))
            task.requisition_count = len(task.requisition_ids)
            task.stock_move_count = len(task.stock_move_ids)

    def _compute_totals(self):
<<<<<<< HEAD
        for task in self:
=======
        # Suma totales aprobados de gastos y sin impuestos de compras confirmadas
        for task in self:
            # Optimización: Usar los campos One2many en vez de consultas search para evitar consultas masivas en BD.

            # Sumar gastos aprobados (post o done).
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            approved_expenses = task.expense_ids.filtered(
                lambda e: e.sheet_id.state in ["post", "done"]
            )
            task.expense_total_approved = sum(
                approved_expenses.mapped("total_amount"))

<<<<<<< HEAD
=======
            # Sumar compras confirmadas (purchase o done).
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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
<<<<<<< HEAD
        purchase_lines = self.env["purchase.order.line"].search(
            [("task_id", "=", self.id)]
        )
        purchase_orders = purchase_lines.mapped("order_id")
=======
        purchase_orders = self.purchase_line_ids.mapped("order_id")
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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

<<<<<<< HEAD
=======
    # ========== FIN MÉTODOS DE ANALYTICS_EXTRA ==========

    # Método que permite cambiar el centro de trabajo al seleccionar un cliente dentro de la tarea.
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.partner_id.centro_trabajo:
                self.centro_trabajo = self.partner_id.centro_trabajo
            else:
                self.centro_trabajo = False

<<<<<<< HEAD
    @api.depends("project_id.is_proyecto_obra")  # ← Dependencia directa
=======
    @api.depends("project_id", "project_id.is_proyecto_obra")
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    def _compute_is_control_obra(self):
        for control in self:
            control.is_control_obra = bool(control.project_id.is_proyecto_obra)

    @api.model
    def default_get(self, fields_list):
<<<<<<< HEAD
        defaults = super(Task, self).default_get(fields_list)

=======
        # 1. Llamamos al metodo original para obtener los defaults estandar
        defaults = super(Task, self).default_get(fields_list)

        # 2. Revisamos si un proyecto viene por defecto en el contexto
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        project_id = defaults.get("project_id") or self.env.context.get(
            "default_project_id"
        )

        if project_id:
<<<<<<< HEAD
            project = self.env["project.project"].browse(project_id)

=======
            # 3. Si tenemos un ID de proyecto, se busca dentro de la Base de datos.
            project = self.env["project.project"].browse(project_id)

            # 4. Asigna el valor del campo is_proyecto_obra del proyecto como el valor por defecto de is_control_obra de la tarea.
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
            if project.is_proyecto_obra:
                defaults["is_control_obra"] = True
            else:
                defaults["is_control_obra"] = False
<<<<<<< HEAD
=======
        # 5. Se devuelven todos los valores por defecto.
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        return defaults

    @api.depends("approver_id")
    def _compute_can_user_approve(self):
<<<<<<< HEAD
=======
        """Comprueba si el usuario actual es el aprobador asignado O tiene permiso global"""
        # Verificamos si el usuario pertenece al grupo de Aprobador Global
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        is_global_approver = self.env.user.has_group(
            'project_modificaciones.permiso_global_aprobar_tarea')

        for task in self:
            if is_global_approver:
                task.can_user_approve = True
            elif task.approver_id:
                task.can_user_approve = (self.env.user == task.approver_id)
            else:
                task.can_user_approve = False

<<<<<<< HEAD
    @api.onchange("centro_trabajo")
    def _onchange_centro_trabajo(self):
=======
    # Dominios eliminados para evitar problemas con IDs inválidos

    @api.onchange("centro_trabajo")
    def _onchange_centro_trabajo(self):
        """
        Limpia los campos dependientes si el CT cambia.
        (Lógica movida de creacion.avances)
        """
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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
<<<<<<< HEAD
        # Corrección: Asegurar que las subtareas hereden el proyecto de su padre
        # antes de que se evalúe cualquier lógica de 'is_control_obra'.
        for vals in vals_list:
            if not vals.get("project_id") and vals.get("parent_id"):
                parent = self.env["project.task"].browse(vals["parent_id"])
                if parent.project_id:
                    vals["project_id"] = parent.project_id.id

        for vals in vals_list:
            if vals.get("sale_line_id"):
                line = self.env["sale.order.line"].browse(vals["sale_line_id"])

                if line.order_id.pending_service_id:
                    vals["name"] = f"{line.order_id.name}: {line.name}"
                elif line.partida:
                    original_name = vals.get("name", "")
                    if line.partida not in original_name:
                        vals["name"] = f"{original_name}-[{line.partida}]"

=======
        sale_lines_by_id = {
            line.id: line
            for line in self.env["sale.order.line"].browse(
                [vals["sale_line_id"] for vals in vals_list if vals.get("sale_line_id")]
            )
        }

        # Ajusta el nombre de la tarea.
        for vals in vals_list:
            # Verificamos si la tarea viene de una línea de venta
            if vals.get("sale_line_id"):
                # Buscamos la línea para obtener la partida
                line = sale_lines_by_id.get(vals["sale_line_id"])

                # Si la orden de venta tiene un servicio pendiente, usar el nombre de la orden
                if line and line.order_id.pending_service_id:
                    # Reemplazar el nombre del pendiente por el nombre de la orden de venta
                    vals["name"] = f"{line.order_id.name}: {line.name}"
                elif line and line.partida:
                    original_name = vals.get("name", "")
                    # Evitamos duplicar si ya se agregó antes
                    if line.partida not in original_name:
                        vals["name"] = f"{original_name}-[{line.partida}]"

        # 1. Obtener etapa de borrador
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        stage_draft = self.env.ref(
            "project_modificaciones.project_task_type_obra_draft", raise_if_not_found=False
        )

<<<<<<< HEAD
        project_ids = [v.get("project_id")
                       for v in vals_list if v.get("project_id")]

=======
        # Obtenemos los IDs de proyecto para consultarlos todos de una sola vez
        project_ids = [v.get("project_id")
                       for v in vals_list if v.get("project_id")]

        # Creamos un mapa: {project_id: is_proyecto_obra}
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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
<<<<<<< HEAD
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

=======
                # 1. Asignar valores por defecto
                vals.update({
                    "approval_state": "draft",
                    "stage_id": (stage_draft.id if stage_draft else vals.get("stage_id")),
                })

                # 2. Intentar calcular el aprobador.
                supervisor_interno_id = vals.get("supervisor_interno")

                # Solo entramos si hay un supervisor asignado
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
                if supervisor_interno_id:
                    supervisor = self.env["hr.employee"].sudo().browse(
                        supervisor_interno_id)
                    approver_user_id = False

<<<<<<< HEAD
                    if supervisor.apropador_tarea_obra:
                        approver_user_id = supervisor.apropador_tarea_obra.user_id.id

                    if not approver_user_id:
                        approver_employee = supervisor.parent_id
=======
                    # Prioridad 1: Aprobador de la tarea de obra (Campo personalizado)
                    if supervisor.apropador_tarea_obra:
                        approver_user_id = supervisor.apropador_tarea_obra.user_id.id

                    # Prioridad 2: Fallback (Solo si no se encontró en el paso 1)
                    if not approver_user_id:
                        approver_employee = supervisor.parent_id  # Gerente
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)

                        if not approver_employee:
                            raise ValidationError(_(
                                "El supervisor %s no tiene configurado un 'Aprobador de Tarea Obra' ni un 'Líder directo'."
                            ) % supervisor.name)

                        if not approver_employee.user_id:
                            raise ValidationError(_(
                                "El Gerente %s del Supervisor %s no tiene usuario asociado."
                            ) % (approver_employee.name, supervisor.name))

                        approver_user_id = approver_employee.user_id.id

<<<<<<< HEAD
                    vals["approver_id"] = approver_user_id

        tasks = super(Task, self).create(vals_list)

=======
                    # Si todo está bien, se asigna el aprobador.
                    vals["approver_id"] = approver_user_id

        # 5. Crear tareas normalmente
        tasks = super(Task, self).create(vals_list)

        # 6. Re-asegurar la etapa de borrador
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        for task in tasks:
            if task.is_control_obra and stage_draft and task.stage_id != stage_draft:
                task.sudo().write({"stage_id": stage_draft.id})

        return tasks

    def _create_approval_activity(self):
<<<<<<< HEAD
=======
        """Crea la actividad de aprobación para el superintendente."""
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
        activity_type_per = self.env.ref(
            "project_modificaciones.aprobacion_mail_activity", raise_if_not_found=False
        )
        if not activity_type_per:
<<<<<<< HEAD
=======
            # Fallback por si la actividad 'To Do' no existe
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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

<<<<<<< HEAD
    def _mark_approval_activity_done(self):
        for task in self:
            if task.approval_activity_id:
                selection_dict = dict(task._fields["approval_state"].selection)
=======
    # Método que permite que la retroalimentación muestre la etiqueta del estado en vez de la clave interna.
    def _mark_approval_activity_done(self):
        """Marca la actividad de aprobación como hecha (aprobada o rechazada)."""
        for task in self:
            if task.approval_activity_id:
                # Obtenemos el diccionario de selecciones del campo
                selection_dict = dict(task._fields["approval_state"].selection)
                # Obtenemos la etiqueta (Label) basada en el estado actual
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
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
<<<<<<< HEAD
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
=======
        """Abre el wizard de rechazo para la tarea seleccionada.
        Corregido: usa ensure_one() para operar sobre un único registro y evitar
        que el return dentro del bucle saltee tareas silenciosamente.
        """
        self.ensure_one()
        is_global = self.env.user.has_group(
            'project_modificaciones.permiso_global_aprobar_tarea')

        if self.approval_state != "to_approve":
            return False
        if self.env.user != self.approver_id and not is_global:
            raise ValidationError(
                _("Solo el aprobador asignado (%s) o un aprobador global pueden rechazar.") % self.approver_id.name)

        return {
            "type": "ir.actions.act_window",
            "res_model": "wizard.rechazado.task",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)

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

<<<<<<< HEAD
    @api.constrains('child_ids', 'use_weighted_progress')
    def _check_subtask_weights(self):
        for task in self:
            if task.use_weighted_progress and task.child_ids:
                total_weight = sum(task.child_ids.mapped('subtask_weight'))
                # Se permite que la suma sea menor o igual a 100%
                # El remanente lo gestiona la tarea padre directamente.
                if total_weight > 100.1:
                    raise ValidationError(_(
                        "La suma de los porcentajes de las subtareas no puede ser mayor al 100%%. "
                        "Suma actual: %s%% en la tarea %s"
                    ) % (total_weight, task.name))

                if total_weight < 100.0:
                    raise ValidationError(_(
                        "La suma de los porcentajes de las subtareas no puede ser menor al 100%%."
                        "Suma actua: %s%% en la tarea %s."
                    ) % (total_weight, task.name))

    # Servicio pediente relacionado con la tarea
=======
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
    servicio_pendiente = fields.Many2one(
        'pending.service',
        string="Servicio Pendiente",
        ondelete="set null",
<<<<<<< HEAD
        help="Servicio pendiente relacionado con la tarea"
    )

    def action_link_sale_line(self):
        """Método para forzar la vinculación correcta con la línea de venta y actualizar entregas."""
        for task in self:
            if task.sale_line_id:
                task.sale_line_id.sudo().write({'task_id': task.id})
                # Trigger recompute manually for safety
                task.sale_line_id._compute_qty_delivered()
        return True
=======
        index=True,
        help="Servicio pendiente relacionado con la tarea."
    )

    @api.constrains('servicio_pendiente', 'planned_date_begin', 'date_deadline')
    def _check_task_dates_within_pending_range(self):
        for task in self:
            pending = task.servicio_pendiente
            if not pending:
                continue

            task_start = task.planned_date_begin
            task_end = task.date_deadline
            pending_start = pending.date_start
            pending_end = pending.date_end_plan

            if task_start and task_end and task_start > task_end:
                raise ValidationError(_(
                    "La fecha de inicio de la tarea no puede ser mayor que la fecha límite."
                ))

            if task_start and pending_start and task_start < pending_start:
                raise ValidationError(_(
                    "La tarea '%(task)s' inicia fuera del rango del servicio pendiente '%(pending)s'. "
                    "Inicio de tarea: %(task_start)s. Inicio permitido: %(pending_start)s."
                ) % {
                    'task': task.display_name,
                    'pending': pending.display_name,
                    'task_start': fields.Datetime.to_string(task_start),
                    'pending_start': fields.Datetime.to_string(pending_start),
                })

            if task_end and pending_end and task_end > pending_end:
                raise ValidationError(_(
                    "La tarea '%(task)s' termina fuera del rango del servicio pendiente '%(pending)s'. "
                    "Fin de tarea: %(task_end)s. Fin permitido: %(pending_end)s."
                ) % {
                    'task': task.display_name,
                    'pending': pending.display_name,
                    'task_end': fields.Datetime.to_string(task_end),
                    'pending_end': fields.Datetime.to_string(pending_end),
                })

    ####################################################
    #### Campos para la vista kanban personalizada. ####
    ####################################################
    days_delayed = fields.Integer(
        string="Días de Retraso",
        compute="_compute_days_delayed",
        store=True,
        help="Días transcurridos desde la Fecha Fin Planeada hasta hoy."
    )

    kanban_begin_short = fields.Char(compute='_compute_kanban_short_dates')
    kanban_deadline_short = fields.Char(compute='_compute_kanban_short_dates')

    is_scaffolding = fields.Boolean(compute='_compute_is_scaffolding')

    def _compute_is_scaffolding(self):
        for task in self:
            is_scaff = False
            if task.sale_line_id and hasattr(task.sale_line_id, 'is_scaffolding') and task.sale_line_id.is_scaffolding:
                is_scaff = True
            task.is_scaffolding = is_scaff

    @api.depends('planned_date_begin', 'date_deadline')
    def _compute_kanban_short_dates(self):
        import pytz
        tz_name = self.env.user.tz or 'America/Mexico_City'
        user_tz = pytz.timezone(tz_name)
        for task in self:
            if task.planned_date_begin:
                dt = task.planned_date_begin.replace(
                    tzinfo=pytz.utc).astimezone(user_tz)
                task.kanban_begin_short = dt.strftime('%d/%m/%y %H:%M')
            else:
                task.kanban_begin_short = ''

            if task.date_deadline:
                dt = task.date_deadline.replace(
                    tzinfo=pytz.utc).astimezone(user_tz)
                task.kanban_deadline_short = dt.strftime('%d/%m/%y %H:%M')
            else:
                task.kanban_deadline_short = ''

    @api.depends('date_deadline', 'state', 'avance_actual')
    def _compute_days_delayed(self):
        today = fields.Date.today()
        for task in self:
            # 1. Extraemos y forzamos a 'Date' puro
            deadline = task.date_deadline
            if deadline and isinstance(deadline, datetime):
                deadline = deadline.date()

            # Si la tarea NO está terminada, el avance físico es < 100%, y tiene fecha vencida
            if task.state != '1_done' and task.avance_actual < 100.0 and deadline and deadline < today:
                delta = today - deadline
                task.days_delayed = delta.days
            else:
                task.days_delayed = 0

    avance_planeado = fields.Float(
        string="Avance Planeado (%)", compute="_compute_avances_kanban", store=True)
    avance_actual = fields.Float(
        string="Avance Físico Real (%)", compute="_compute_avances_kanban", store=True)
    avance_facturado = fields.Float(
        string="Avance Facturado (%)", compute="_compute_avances_kanban", store=True)

    kanban_color_obra = fields.Selection([
        ('green', 'Verde  — En tiempo o adelantado'),
        ('amber', 'Ámbar  — Retraso menor al 10 %'),
        ('red',   'Rojo   — Retraso crítico o fecha vencida'),
    ], string="Semáforo Control Obra",
        compute="_compute_avances_kanban",
        store=True,
        group_expand='_read_group_kanban_color_obra',
    )

    @api.depends('planned_date_begin', 'date_deadline', 'progress', 'qty_invoiced', 'sale_order_id', 'total_pieces', 'state', 'piezas_pendientes', 'quant_progress')
    def _compute_avances_kanban(self):
        today = fields.Date.today()
        for task in self:
            # --- 1. Avance Físico Actual ---
            if task.sale_order_id and task.total_pieces > 0:
                valor_fisico = float(
                    task.quant_progress * 100) / task.total_pieces
                task.avance_actual = round(valor_fisico, 2)
            elif not task.sale_order_id and task.piezas_pendientes > 0:
                valor_fisico = float(
                    task.quant_progress * 100) / task.piezas_pendientes
                task.avance_actual = round(valor_fisico, 2)
            else:
                task.avance_actual = 0.0

            # --- 2. Avance Planeado ---
            start_date = task.planned_date_begin
            if start_date and isinstance(start_date, datetime):
                start_date = start_date.date()

            end_date = task.date_deadline
            if end_date and isinstance(end_date, datetime):
                end_date = end_date.date()

            if start_date and end_date and start_date <= end_date:
                total_days = (end_date - start_date).days
                if total_days > 0:
                    days_passed = (today - start_date).days
                    if days_passed <= 0:
                        task.avance_planeado = 0.0
                    elif days_passed >= total_days:
                        task.avance_planeado = 100.0
                    else:
                        valor_planeado = (days_passed / total_days) * 100.0
                        task.avance_planeado = round(valor_planeado, 2)
                else:
                    task.avance_planeado = 100.0 if today >= end_date else 0.0
            else:
                task.avance_planeado = 0.0

            # --- 3. Avance Facturado ---
            if task.quant_progress > 0:
                fact_pct = (task.qty_invoiced / task.quant_progress) * 100.0
                task.avance_facturado = round(min(100.0, fact_pct), 2)
            else:
                task.avance_facturado = 0.0

            # --- 4. Semáforo ---
            if task.state == '1_done' or task.avance_actual >= 100.0:
                task.kanban_color_obra = 'green'
            elif end_date and today > end_date:
                task.kanban_color_obra = 'red'
            else:
                diff = round(task.avance_planeado - task.avance_actual, 2)
                if diff <= 0:
                    task.kanban_color_obra = 'green'
                elif diff < 10.0:
                    task.kanban_color_obra = 'amber'
                else:
                    task.kanban_color_obra = 'red'

    def action_recompute_progress_metrics(self):
        """Recalcula los campos de avance y semáforo para tareas seleccionadas."""
        for task in self:
            task = task.sudo()
            if not task.id:
                continue

            # Recalcular primero los avances físicos base.
            task._units()
            task._progress()
            task._compute_avances_kanban()
            task._compute_days_delayed()
            task._compute_task_kanban_stage()
            task._update_completion_state()

        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cálculo Completado',
                    'message': 'Las métricas se han actualizado correctamente.',
                    'sticky': False, # Si es False, desaparece solo después de unos segundos
                    'type': 'success', # Verde
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                }
            }

    @api.model
    def _read_group_kanban_color_obra(self, colors, domain, read_group_order=None):
        """
        Forzar a Odoo a renderizar siempre las columnas del Semáforo en el Kanban
        aunque no existan registros para ese color específico.
        """
        # Definimos el orden exacto en el que quieres que aparezcan las columnas de izquierda a derecha
        # En este caso: Rojo -> Ámbar -> Verde
        return ['red', 'amber', 'green']

    # -------------------------------------------------------------------------
    # KANBAN STAGE — 5 columnas para project.task (Control Obra)
    # Columnas extra: Cancelada y Completada (estados terminales del ciclo de obra)
    # Las 3 centrales derivan de kanban_color_obra (semáforo intacto)
    # -------------------------------------------------------------------------
    kanban_stage = fields.Selection(
        selection=[
            ('no_plan',    '📋 Sin Planeación'),
            ('red',        '🔴 Retraso Crítico'),
            ('amber',      '🟡 Retraso Menor'),
            ('green',      '🟢 En Tiempo'),
            ('completed',  '✅ Completada'),
        ],
        string='Columna Kanban',
        compute='_compute_task_kanban_stage',
        store=True,
        group_expand='_read_group_task_kanban_stage',
        help=(
            "Campo de agrupación del Kanban con 5 columnas.\n"
            "Sin Planeación: sin fecha inicio planeada o sin fecha límite.\n"
            "Completada: state = 1_done.\n"
            "Rojo/Ámbar/Verde: deriva del semáforo para tareas en curso."
        ),
    )

    @api.depends('state', 'kanban_color_obra', 'planned_date_begin', 'date_deadline', 'avance_actual')
    def _compute_task_kanban_stage(self):
        """Asigna la columna kanban de 5 etapas para project.task.

        Lógica de prioridad:
        1. Avance físico >= 100.0 o state='1_done' → 'completed'
        2. Sin fecha inicio o fecha límite         → 'no_plan' (aún sin planear)
        3. Resto                                   → hereda kanban_color_obra (red/amber/green)
        """
        for task in self:
            if task.avance_actual >= 100.0 or task.state == '1_done':
                task.kanban_stage = 'completed'
            elif not task.planned_date_begin or not task.date_deadline:
                task.kanban_stage = 'no_plan'
            else:
                task.kanban_stage = task.kanban_color_obra or 'red'

    @api.model
    def _read_group_task_kanban_stage(self, stages, domain, order):
        """Siempre mostrar las 5 columnas aunque alguna esté vacía."""
        return ['no_plan', 'red', 'amber', 'green', 'completed']
>>>>>>> 9d09621 (Vista Unificada Gestion de Proyectos y Fusion de servicios pendientes.)
