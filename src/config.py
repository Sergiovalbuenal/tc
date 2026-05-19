# -*- coding: utf-8 -*-
"""Configuración chica y fácil de tocar.

La idea es no esconder reglas del negocio dentro de las páginas. Si mañana
cambian los nombres de columnas o los tipos de movimiento, este archivo es el
primer lugar donde mirar.
"""

from __future__ import annotations

APP_NAME = "Tablero de Control"
APP_VERSION = "2.0"

# Campos estándar que usa el modelo interno del dashboard.
STANDARD_FIELDS = {
    "fecha": "Fecha",
    "monto": "Monto",
    "tipo": "Tipo de movimiento",
    "categoria": "Categoría",
    "subcategoria": "Subcategoría",
    "cuenta": "Cuenta",
    "descripcion": "Descripción",
    "moneda": "Moneda",
}

REQUIRED_FIELDS = ("fecha", "monto")

DEFAULT_CURRENCY = "USD"

# Palabras comunes que usamos para adivinar el mapeo de columnas al cargar datos.
FIELD_ALIASES = {
    "fecha": [
        "fecha", "date", "transaction_date", "fecha_transaccion", "fecha_movimiento",
        "periodo", "created_at", "posted_date", "posting_date",
    ],
    "monto": [
        "monto", "amount", "valor", "importe", "total", "saldo", "value",
        "debe", "haber", "balance", "transaction_amount",
    ],
    "tipo": [
        "tipo", "type", "movimiento", "naturaleza", "clase", "operacion",
        "transaction_type", "ingreso_egreso",
    ],
    "categoria": [
        "categoria", "category", "rubro", "grupo", "concepto", "linea",
        "clasificacion", "cost_center",
    ],
    "subcategoria": [
        "subcategoria", "sub_category", "subcategory", "subrubro", "detalle_categoria",
    ],
    "cuenta": [
        "cuenta", "account", "banco", "wallet", "caja", "origen", "source",
    ],
    "descripcion": [
        "descripcion", "description", "detalle", "memo", "nota", "observacion",
        "glosa", "concepto_detalle",
    ],
    "moneda": [
        "moneda", "currency", "divisa", "iso_currency", "coin",
    ],
}

INCOME_WORDS = {
    "ingreso", "ingresos", "income", "revenue", "venta", "ventas", "cobro",
    "deposito", "depósito", "entrada", "abono", "credit", "credito", "crédito",
}

EXPENSE_WORDS = {
    "egreso", "egresos", "gasto", "gastos", "expense", "expenses", "pago",
    "salida", "retiro", "debit", "debito", "débito", "compra", "compras",
}

ADJUSTMENT_WORDS = {
    "ajuste", "adjustment", "transferencia", "transfer", "traslado",
}

# Esquemas por tipo de dataset: campos, aliases y campos obligatorios.
DATASET_SCHEMAS: dict[str, dict] = {
    "financiero": {
        "label": "Financiero / Contable",
        "icon": "💰",
        "description": "Transacciones, ingresos, egresos, movimientos bancarios",
        "fields": STANDARD_FIELDS,
        "required": ["fecha", "monto"],
        "aliases": FIELD_ALIASES,
    },
    "ventas": {
        "label": "Ventas / Facturación",
        "icon": "🛒",
        "description": "Órdenes de venta, facturas, clientes, productos",
        "fields": {
            "fecha": "Fecha de venta",
            "producto": "Producto / Servicio",
            "cliente": "Cliente",
            "cantidad": "Cantidad",
            "precio": "Precio Unitario",
            "total": "Total / Monto",
            "categoria": "Categoría",
            "vendedor": "Vendedor",
            "region": "Región / Zona",
            "estado": "Estado del pedido",
        },
        "required": ["fecha", "total"],
        "aliases": {
            "fecha": ["fecha", "date", "fecha_venta", "order_date", "sale_date", "fecha_pedido", "fecha_factura"],
            "producto": ["producto", "product", "item", "articulo", "servicio", "service", "nombre_producto", "descripcion_producto"],
            "cliente": ["cliente", "customer", "client", "comprador", "buyer", "razon_social", "nombre_cliente"],
            "cantidad": ["cantidad", "quantity", "qty", "unidades", "units", "cant", "volumen"],
            "precio": ["precio", "price", "precio_unitario", "unit_price", "valor_unitario", "precio_venta"],
            "total": ["total", "amount", "monto", "valor_total", "subtotal", "importe", "revenue", "venta_total", "valor", "factura"],
            "categoria": ["categoria", "category", "rubro", "linea", "grupo", "tipo_producto", "familia"],
            "vendedor": ["vendedor", "seller", "sales_rep", "asesor", "agente", "comercial", "representante"],
            "region": ["region", "zona", "area", "territory", "ciudad", "city", "departamento", "pais"],
            "estado": ["estado", "status", "estado_pedido", "order_status", "situacion", "etapa"],
        },
    },
    "rrhh": {
        "label": "RRHH / Nómina",
        "icon": "👥",
        "description": "Empleados, salarios, departamentos, cargos",
        "fields": {
            "nombre": "Nombre del empleado",
            "cargo": "Cargo / Posición",
            "departamento": "Departamento",
            "salario": "Salario",
            "fecha_ingreso": "Fecha de ingreso",
            "estado": "Estado (activo/inactivo)",
            "genero": "Género",
            "sede": "Sede / Oficina",
        },
        "required": ["nombre", "salario"],
        "aliases": {
            "nombre": ["nombre", "name", "empleado", "employee", "trabajador", "worker", "full_name", "nombre_completo"],
            "cargo": ["cargo", "position", "title", "puesto", "rol", "role", "job_title", "cargo_actual", "ocupacion"],
            "departamento": ["departamento", "department", "area", "division", "sector", "gerencia", "vicepresidencia"],
            "salario": ["salario", "salary", "sueldo", "wage", "compensacion", "compensation", "remuneracion", "salario_basico", "ingreso_mensual"],
            "fecha_ingreso": ["fecha_ingreso", "hire_date", "start_date", "fecha_inicio", "ingreso", "fecha_vinculacion", "antiguedad"],
            "estado": ["estado", "status", "activo", "active", "situacion", "vinculacion", "tipo_contrato"],
            "genero": ["genero", "gender", "sexo", "sex"],
            "sede": ["sede", "office", "location", "ubicacion", "ciudad", "site", "planta", "regional"],
        },
    },
    "inventario": {
        "label": "Inventario / Logística",
        "icon": "📦",
        "description": "Productos, stock, proveedores, pedidos",
        "fields": {
            "producto": "Producto / SKU",
            "categoria": "Categoría",
            "stock": "Cantidad en stock",
            "precio": "Precio unitario",
            "proveedor": "Proveedor",
            "fecha": "Fecha de actualización",
            "bodega": "Bodega / Almacén",
            "estado": "Estado",
        },
        "required": ["producto", "stock"],
        "aliases": {
            "producto": ["producto", "product", "sku", "item", "articulo", "codigo", "code", "referencia", "ref", "nombre_producto"],
            "categoria": ["categoria", "category", "tipo", "type", "familia", "family", "grupo", "linea"],
            "stock": ["stock", "cantidad", "quantity", "inventario", "disponible", "available", "units", "existencias", "saldo"],
            "precio": ["precio", "price", "costo", "cost", "valor", "value", "precio_compra", "costo_unitario"],
            "proveedor": ["proveedor", "supplier", "vendor", "fabricante", "manufacturer", "marca", "brand"],
            "fecha": ["fecha", "date", "fecha_actualizacion", "last_update", "updated_at", "fecha_registro", "fecha_compra"],
            "bodega": ["bodega", "almacen", "warehouse", "deposito", "location", "ubicacion", "bodega_almacen"],
            "estado": ["estado", "status", "condicion", "condition", "disponibilidad", "activo"],
        },
    },
    "general": {
        "label": "Datos Generales",
        "icon": "📊",
        "description": "Datos tabulares sin categoría específica detectada",
        "fields": {},
        "required": [],
        "aliases": {},
    },
}
