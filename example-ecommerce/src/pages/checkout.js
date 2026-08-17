// src/pages/checkout.js
import { useState } from 'react';

export default function Checkout() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleCheckout = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId: 'prod_123', orderId: 'ord_456' })
      });

      const data = await res.json();
      setMessage(data.message);
    } catch (err) {
      setMessage('Error processing checkout');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '50px', fontFamily: 'sans-serif' }}>
      <h1>Checkout - Limited Edition Sneakers</h1>
      <p>Termina tu compra haciendo clic en el botón de abajo. (⚠️ Advertencia: Este código tiene bugs a propósito para probar SDLC Agents)</p>
      
      <form onSubmit={handleCheckout}>
        <button 
          type="submit" 
          disabled={loading}
          style={{
            padding: '10px 20px',
            backgroundColor: '#0070f3',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Procesando...' : 'Confirmar Orden'}
        </button>
      </form>

      {message && (
        <div style={{ marginTop: '20px', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', backgroundColor: '#f9f9f9' }}>
          <strong>Respuesta del servidor: </strong> {message}
        </div>
      )}
    </div>
  );
}
