# Estándares de Seguridad y Privacidad (PinApp)

## 1. Manejo de Secretos (Secrets)
Está determinantemente prohibido (Política de Tolerancia Cero) incluir claves privadas, tokens de API, contraseñas o cualquier otro secreto "hardcodeado" dentro del código fuente. Todos los secretos deben consumirse a través de variables de entorno (`process.env` u `os.environ`) inyectadas por el sistema de CI/CD o el orquestador.

## 2. Protección de PII (Personally Identifiable Information)
Cualquier dato que pueda identificar a un usuario (correo electrónico, dirección, teléfono, datos de tarjeta de crédito) no debe registrarse en los logs de la aplicación. 
Si se debe registrar un objeto que contiene PII, los campos sensibles deben enmascararse utilizando la función de utilidad interna `MaskingService.maskPII()`.

## 3. Consultas a Base de Datos
Todas las consultas a la base de datos deben utilizar consultas parametrizadas o un ORM aprobado. La concatenación directa de strings de entrada de usuario en queries SQL/NoSQL está prohibida para prevenir inyecciones.
