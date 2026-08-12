// Configuración de la web de carga de campo.
// La ANON KEY es la llave PÚBLICA de Supabase: es SEGURA de exponer en el
// navegador. La seguridad la da RLS (schema_v8.sql): con esta llave solo se
// puede CREAR cargas y SUBIR archivos, nunca leer ni borrar.
window.PCC_CONFIG = {
  SUPABASE_URL: "https://nvsnovulwtnbgopyiyal.supabase.co",
  SUPABASE_ANON_KEY: "sb_publishable_MQgyENSPp0QoG34iNk9A7A_VdcOeHt8",
  // Código de acceso opcional para técnicos. Vacío = abierto (como hoy).
  // Si pones un valor, se pide antes de mostrar el formulario.
  ACCESS_CODE: ""
};
