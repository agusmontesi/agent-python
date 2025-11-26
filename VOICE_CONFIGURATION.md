# Configuración de Voces

Las voces de los agentes se pueden configurar fácilmente mediante variables de entorno en el archivo `.env.local`.

## Configuración

### Paso 1: Editar `.env.local`

Abre el archivo `.env.local` (o créalo si no existe) y agrega las siguientes variables:

```env
# Voces de los agentes (Cartesia Sonic-3 Voice IDs)
# Cada agente tiene una voz única verificada de la biblioteca oficial de Cartesia
# Puedes encontrar más voces en: https://docs.livekit.io/agents/models/tts/

# Voz del Moderador - Jacqueline (Confident, young American adult female)
VOICE_MODERATOR=9626c31c-bec5-4cca-baa8-f8ba9e84c8bc

# Voz del CFO - Blake (Energetic American adult male)
VOICE_CFO=a167e0f3-df7e-4d52-a9c3-f949145efdab

# Voz del Director de Finanzas - Robyn (Neutral, mature Australian female)
VOICE_FINANCE_DIRECTOR=f31cc6a7-c1e8-4764-980c-60a361443dd1

# Voz del Director de Ventas - (Energetic voice for sales)
VOICE_SALES_DIRECTOR=694c83e2-8895-4a98-bd16-56332ca3f449

# Voz del Director de Marketing - Daniela (Calm and trusting Mexican female)
VOICE_MARKETING_DIRECTOR=5c5ad5e7-1020-476b-8b91-fdcbe9cc313c
```

### Paso 2: Cambiar las voces

Simplemente reemplaza los valores de las variables con los IDs de las voces que desees usar. Los valores por defecto se mantendrán si no especificas una variable.

### Paso 3: Reiniciar el agente

Después de cambiar las voces en `.env.local`, reinicia el agente para que los cambios surtan efecto.

## Encontrar IDs de voces

Puedes encontrar más voces disponibles en la documentación de LiveKit:
- [Documentación de TTS de LiveKit](https://docs.livekit.io/agents/models/tts/)
- [Cartesia Sonic-3 Voices](https://docs.cartesia.ai/voice-cloning/voice-library)

## Notas

- Si no especificas una variable de entorno, se usará el valor por defecto del código
- Los cambios en `.env.local` requieren reiniciar el agente
- Cada agente puede tener una voz diferente para facilitar la identificación

