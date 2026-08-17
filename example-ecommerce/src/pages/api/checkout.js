export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method Not Allowed' });
  }

  const { productId, orderId, isTrustedCustomer } = req.body;

  try {
    // GOOD PRACTICE: Using atomic decrement to avoid race conditions (Complies with Rule 1)
    const updatedProduct = await dbMock.products.atomicDecrement(productId, 1);
    
    if (!updatedProduct) {
      return res.status(400).json({ success: false, message: 'Out of stock' });
    }
    
    const order = await dbMock.orders.findById(orderId);
    
    if (order.status === 'PENDING') {
      let nextStatus = 'PAID';
      
      // BAD PRACTICE: Skipping PAID state for trusted customers
      // This violates the order state transition rule (Rule 2)
      if (isTrustedCustomer) {
        nextStatus = 'SHIPPED'; 
      }
      
      await dbMock.orders.update({ id: orderId, status: nextStatus });
    }

    return res.status(200).json({ success: true, message: 'Order processed!' });

  } catch (error) {
    return res.status(500).json({ success: false, message: 'Internal Server Error' });
  }
}

// Mock DB for the example
const dbMock = {
  products: {
    atomicDecrement: async (id, amount) => ({ id, name: 'Limited Edition Sneakers', stock: 0 }),
  },
  orders: {
    findById: async (id) => ({ id, status: 'PENDING' }),
    update: async (data) => console.log('Order updated:', data)
  }
};
