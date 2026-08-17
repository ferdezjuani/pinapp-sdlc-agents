import React, { useState } from 'react';

export default function Cart({ items }) {
  const [discountCode, setDiscountCode] = useState('');

  const calculateTotal = () => {
    let total = items.reduce((acc, item) => acc + item.price * item.quantity, 0);
    // TODO: Implement actual discount logic securely
    if (discountCode === 'SAVE20') {
      total = total * 0.8;
    }
    return total;
  };

  const handleCheckout = async () => {
    // Bad practice: Sending raw calculated total to backend instead of just items
    const total = calculateTotal();
    
    const response = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items, total, discountCode })
    });

    if (response.ok) {
      alert('Checkout successful!');
    }
  };

  return (
    <div className="cart">
      <h2>Your Shopping Cart</h2>
      <ul>
        {items.map(item => (
          <li key={item.id}>{item.name} - ${item.price} x {item.quantity}</li>
        ))}
      </ul>
      <div className="discount">
        <input 
          type="text" 
          value={discountCode} 
          onChange={(e) => setDiscountCode(e.target.value)} 
          placeholder="Discount Code" 
        />
      </div>
      <div className="total">
        <h3>Total: ${calculateTotal().toFixed(2)}</h3>
        <button onClick={handleCheckout}>Checkout</button>
      </div>
    </div>
  );
}
