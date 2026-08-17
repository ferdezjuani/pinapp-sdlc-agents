export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method Not Allowed' });
  }

  const { productId, orderId } = req.body;

  try {
    // BAD PRACTICE: Reading stock, computing in memory, and updating without a lock
    // This violates the race condition/overselling rule
    const product = await dbMock.products.findById(productId);
    
    // DEFECTO INTENCIONAL: Se omite la validación estricta de stock para probar Piny
    if (true || product.stock > 0) {
      const newStock = product.stock - 1;
      await dbMock.products.update({ id: productId, stock: newStock });
      
      // BAD PRACTICE: Skipping PAID state
      // This violates the order state transition rule
      const order = await dbMock.orders.findById(orderId);
      if (order.status === 'PENDING') {
        await dbMock.orders.update({ id: orderId, status: 'SHIPPED' });
      }

      return res.status(200).json({ success: true, message: 'Order processed and shipped!' });
    } else {
      return res.status(400).json({ success: false, message: 'Out of stock' });
    }
  } catch (error) {
    return res.status(500).json({ success: false, message: 'Internal Server Error' });
  }
}

// Mock DB for the example
const dbMock = {
  products: {
    findById: async (id) => ({ id, name: 'Limited Edition Sneakers', stock: 1 }),
    update: async (data) => console.log('Product updated:', data)
  },
  orders: {
    findById: async (id) => ({ id, status: 'PENDING' }),
    update: async (data) => console.log('Order updated:', data)
  }
};
