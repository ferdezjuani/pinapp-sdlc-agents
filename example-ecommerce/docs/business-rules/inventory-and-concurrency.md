# Reglas de Inventario y Concurrencia

Este documento define las políticas críticas del negocio relacionadas con el manejo del stock y los ciclos de vida de las órdenes en la plataforma de e-commerce. Cualquier PR que modifique código relacionado a órdenes o inventario debe adherirse estrictamente a estas reglas.

## 1. Prevención de Sobreventa (Race Conditions)
Al momento de finalizar el proceso de checkout y descontar stock, **siempre se debe usar un mecanismo de bloqueo transaccional en la base de datos**.

*   **Razón:** En plataformas con alta concurrencia, dos usuarios pueden intentar comprar la última unidad disponible exactamente al mismo tiempo. Si se lee el stock y se actualiza en dos queries separadas sin bloqueo, ambos usuarios lograrán la compra y se producirá una venta sin stock (sobreventa).
*   **Implementación:**
    *   Si se usa SQL, emplear transacciones atómicas con `SELECT ... FOR UPDATE` al consultar la cantidad actual del producto.
    *   Si se usa NoSQL u ORMs modernos, asegurar el uso de operaciones atómicas de decremento (por ejemplo `$inc: { stock: -1 }` en MongoDB) u Optimistic Concurrency Control (OCC).
    *   **Nunca** leer el stock en memoria, calcular el nuevo stock y luego hacer un simple `UPDATE` sin bloqueos.

## 2. Transición de Estados del Pedido
La máquina de estados de las órdenes es estricta para propósitos contables y de logística.

*   **Razón:** Un paquete no puede ser entregado o enviado a logística si el dinero no ha sido exitosamente cobrado.
*   **Implementación:**
    *   Un pedido recién creado ingresa en estado `PENDING`.
    *   Un pedido en estado `PENDING` **jamás** puede transicionar directamente al estado `SHIPPED` o `DELIVERED`.
    *   Debe existir obligatoriamente una transición intermedia por el estado `PAID` (o equivalente) que es gatillada únicamente por el webhook del procesador de pagos al confirmar el cobro exitoso.
    *   Si el pago falla, la orden debe transicionar de `PENDING` a `CANCELLED` o `PAYMENT_FAILED`.
