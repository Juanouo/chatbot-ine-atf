# Guía de instalación y uso local

> **Para quién es esta guía:** Estudiantes de posgrado sin experiencia previa en Docker, SQL ni línea de comandos. Solo necesitas saber usar un navegador web y tener paciencia en la primera instalación.

---

## Índice

1. [¿Qué vamos a hacer?](#1-qué-vamos-a-hacer)
2. [Instalaciones previas (solo la primera vez)](#2-instalaciones-previas-solo-la-primera-vez)
3. [Descargar los archivos del proyecto](#3-descargar-los-archivos-del-proyecto)
4. [Configurar tu clave de API](#4-configurar-tu-clave-de-api)
5. [Primera puesta en marcha](#5-primera-puesta-en-marcha)
6. [Usar el chatbot](#6-usar-el-chatbot)
7. [Apagar el proyecto](#7-apagar-el-proyecto)
8. [Uso diario](#8-uso-diario)
9. [Solución de problemas](#9-solución-de-problemas)

---

## 1. ¿Qué vamos a hacer?

Este proyecto es un **chatbot** que responde preguntas sobre estadísticas chilenas (empleo y delincuencia) consultando directamente una base de datos. En vez de buscar tablas en PDFs del INE, simplemente puedes escribir: *"¿Cuál fue la tasa de desocupación en la Región Metropolitana en 2023?"* y el sistema te responde automáticamente.

Para que esto funcione en tu computador necesitas instalar una sola herramienta: **Docker**. Docker es como un "contenedor de software" que empaqueta el chatbot, la base de datos y todo lo necesario para que funcione igual en cualquier computador, sin importar si tienes Mac o Windows.

**Analogía:** Si alguna vez has usado R con `renv` o Python con entornos virtuales, Docker hace algo similar pero a nivel de toda la aplicación.

---

## 2. Instalaciones previas (solo la primera vez)

### 2.1 Instalar Docker Desktop

Docker Desktop es la única instalación principal que necesitas.

---

#### macOS

1. Ve a [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Haz clic en **"Download for Mac"**
   - Si tu Mac tiene chip Apple Silicon (M1, M2, M3, M4): descarga la versión **"Mac with Apple Silicon"**
   - Si tu Mac es Intel: descarga **"Mac with Intel Chip"**
   - ¿No sabes cuál tienes? Haz clic en el menú  → "Acerca de este Mac" → busca "Chip" o "Procesador"
3. Abre el archivo `.dmg` descargado y arrastra Docker al directorio **Aplicaciones**
4. Abre Docker desde Aplicaciones. La primera vez pedirá tu contraseña de administrador.
5. Espera a que el ícono de la ballena 🐳 en la barra de menú deje de moverse. Cuando esté quieto, Docker está listo.

---

#### Windows

En Windows, Docker Desktop funciona con **WSL 2** (Windows Subsystem for Linux), que es una capa de Linux que corre dentro de Windows. Docker la instala automáticamente.

**Requisito previo:** Windows 10 versión 1903 o superior, o Windows 11.

1. Ve a [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Haz clic en **"Download for Windows"**
3. Ejecuta el instalador `Docker Desktop Installer.exe`
4. Durante la instalación, asegúrate de que esté marcada la opción **"Use WSL 2 instead of Hyper-V"**
5. Si Windows pide reiniciar, hazlo.
6. Después de reiniciar, abre Docker Desktop desde el menú Inicio.
7. La primera vez puede pedirte que instales una actualización del kernel de WSL 2. Acepta y sigue las instrucciones.
8. Espera a que el ícono de la ballena 🐳 en la barra de tareas (abajo a la derecha) deje de moverse.

---

### 2.2 Abrir la terminal

La **terminal** (también llamada "línea de comandos" o "consola") es donde vas a escribir los comandos para iniciar y detener el proyecto. No te preocupes: solo necesitarás unos pocos comandos simples.

---

#### macOS

La terminal viene preinstalada en macOS.

- Presiona `Cmd + Espacio` y escribe **"Terminal"**, luego presiona Enter
- O búscala en Aplicaciones → Utilidades → Terminal

Verás una ventana con texto y un cursor. Ahí se escriben los comandos.

---

#### Windows

En Windows usaremos **PowerShell**, que viene preinstalado.

- Presiona `Win + X` y selecciona **"Windows PowerShell"** o **"Terminal"**
- O busca "PowerShell" en el menú Inicio

> **Nota:** También puedes usar el terminal que viene dentro de Docker Desktop: abre Docker Desktop → icono de la ballena → Settings → Resources → WSL Integration. Pero PowerShell es más sencillo para lo que necesitamos.

---

## 3. Descargar los archivos del proyecto

### Opción A: Descargar como archivo ZIP (más simple)

Si prefieres trabajar con un archivo `.zip` con el proyecto:

1. Descarga el archivo ZIP a tu computador
2. Extrae (descomprime) el archivo en una ubicación que recuerdes, por ejemplo:
   - macOS: `/Users/tu_nombre/proyectos/chatbot`
   - Windows: `C:\Users\tu_nombre\proyectos\chatbot`
3. Toma nota de esa ruta, la necesitarás luego.

### Opción B: Clonar con Git

Si te animas a trabajar con Git y acceso al repositorio:

**macOS** (en la Terminal):
```bash
git clone <URL_DEL_REPOSITORIO>
cd open-webui
```

**Windows** (en PowerShell):
```powershell
git clone <URL_DEL_REPOSITORIO>
cd open-webui
```

---

## 4. Configurar tu clave de API

El chatbot usa un servicio externo de inteligencia artificial (OpenRouter) para interpretar tus preguntas y convertirlas en consultas a la base de datos. Para esto necesitas una **clave de API**, que es como una contraseña personalizada que identifica tu cuenta.

### 4.1 Crear una cuenta en OpenRouter

1. Ve a [https://openrouter.ai](https://openrouter.ai)
2. Haz clic en **"Sign In"** → **"Create account"**
3. Puedes registrarte con tu cuenta de Google o con email
4. Una vez dentro, ve a la sección **"API Keys"** (en el menú de tu perfil, arriba a la derecha)
5. Haz clic en **"Create Key"**, ponle un nombre (ej: "chatbot-tesis") y copia la clave

La clave se verá así: `sk-or-v1-abc123def456...` (una cadena larga de caracteres).

> **Importante:** Esta clave es como una contraseña. No la compartas públicamente ni la subas a repositorios de código.

### 4.2 Agregar créditos (si es necesario)

OpenRouter es de pago, pero muy económico para uso de investigación. Los modelos que usa este proyecto cuestan fracciones de centavo por consulta. Con USD $5 tienes para cientos de consultas.

1. En OpenRouter, ve a **"Credits"**
2. Agrega la cantidad que quieras (mínimo USD $5 recomendado)

### 4.3 Crear el archivo de configuración `.env`

Este archivo le dice al proyecto tu clave de API y otras configuraciones. **Debes crearlo manualmente** (no viene incluido por razones de seguridad).

---

#### macOS

En la Terminal, navega a la carpeta del proyecto y crea el archivo:

```bash
# Primero ve a la carpeta del proyecto (ajusta la ruta según donde lo guardaste)
cd ~/proyectos/chatbot/open-webui

# Crea el archivo .env con un editor de texto simple
nano .env
```

Se abrirá un editor de texto en la terminal. Escribe exactamente lo siguiente, reemplazando `TU_CLAVE_AQUI` por tu clave real de OpenRouter:

```
LLM_SERVICE=openrouter
OPENAI_MODEL=qwen/qwen3-32b
OPENAI_API_KEY=TU_CLAVE_AQUI
OPENAI_API_BASE_URL="https://openrouter.ai/api/v1"
ENABLE_PERSISTENT_CONFIG=True
GLOBAL_LOG_LEVEL=20
```

Para guardar y salir de `nano`: presiona `Ctrl + X`, luego `Y`, luego `Enter`.

---

#### Windows

En PowerShell, navega a la carpeta del proyecto y crea el archivo:

```powershell
# Primero ve a la carpeta del proyecto (ajusta la ruta según donde lo guardaste)
cd C:\Users\tu_nombre\proyectos\chatbot\open-webui

# Crea el archivo .env
notepad .env
```

Se abrirá el Bloc de notas. Escribe exactamente lo siguiente, reemplazando `TU_CLAVE_AQUI` por tu clave real:

```
LLM_SERVICE=openrouter
OPENAI_MODEL=qwen/qwen3-32b
OPENAI_API_KEY=TU_CLAVE_AQUI
OPENAI_API_BASE_URL="https://openrouter.ai/api/v1"
ENABLE_PERSISTENT_CONFIG=True
GLOBAL_LOG_LEVEL=20
```

Guarda el archivo con `Ctrl + S` y cierra el Bloc de notas.

> **Importante:** Asegúrate de que el archivo se llame `.env` (con punto al principio) y **no** `.env.txt`. Si Windows agrega `.txt` automáticamente, renómbralo quitando esa extensión.

---

## 5. Primera puesta en marcha

Esta sección solo se hace **una vez**. Las veces siguientes es mucho más rápido (ver sección [Uso diario](#8-uso-diario)).

### 5.1 Abrir la terminal en la carpeta del proyecto

---

#### macOS

```bash
cd ~/proyectos/chatbot/open-webui
```

Verifica que estás en el lugar correcto listando los archivos:
```bash
ls
```

Deberías ver archivos como `Makefile`, `docker-compose.yml`, `postgres_llm_tool.py`, etc.

---

#### Windows

```powershell
cd C:\Users\tu_nombre\proyectos\chatbot\open-webui
```

Verifica que estás en el lugar correcto:
```powershell
dir
```

Deberías ver archivos como `Makefile`, `docker-compose.yml`, `postgres_llm_tool.py`, etc.

---

### 5.2 Crear la red de Docker (solo una vez en toda la vida)

Este paso crea una "red virtual" interna para que los componentes del proyecto se comuniquen entre sí.

---

#### macOS

```bash
make network-create
```

Deberías ver: `Creating webui-net network...`

---

#### Windows

```powershell
docker network create webui-net
```

Si responde `Error: network with name webui-net already exists`, no hay problema: ya existe y puedes continuar.

---

### 5.3 Iniciar el proyecto por primera vez

Este paso descarga todas las imágenes necesarias y construye los contenedores. **La primera vez puede tardar entre 5 y 20 minutos** dependiendo de tu conexión a internet, ya que descarga varios gigabytes. Las veces siguientes tarda solo 30-60 segundos.

---

#### macOS

```bash
make prod-up
```

---

#### Windows

```powershell
docker compose --profile prod up -d
```

---

Verás mucho texto pasando en pantalla. Eso es normal: Docker está descargando e instalando todo.

### 5.4 Verificar que todo esté funcionando

Una vez que el comando anterior termine y vuelva el cursor, verifica el estado de los contenedores:

---

#### macOS

```bash
make status
```

---

#### Windows

```powershell
docker ps
```

---

Deberías ver tres contenedores con estado **"Up"** (o "running"):
- `open-webui-prod`
- `toy-postgres-prod`
- `ollama-prod`

Si aparecen los tres, ¡todo está funcionando!

### 5.5 Esperar a que el chatbot esté listo

Aunque los contenedores estén activos, el chatbot necesita aproximadamente **1-2 minutos** para terminar su configuración interna. Si entras demasiado pronto, puede que no funcione correctamente.

Puedes ver el progreso con:

---

#### macOS

```bash
make prod-logs
```

---

#### Windows

```powershell
docker compose --profile prod logs -f
```

---

Espera hasta ver un mensaje similar a: `✅ Open WebUI startup complete!`

Para detener los logs: presiona `Ctrl + C` (esto **no** apaga el proyecto, solo deja de mostrar los logs).

---

## 6. Usar el chatbot

### 6.1 Abrir el chatbot en el navegador

Abre tu navegador (Chrome, Firefox, Safari, etc.) y ve a:

**http://localhost:3030**

### 6.2 Crear tu cuenta

La primera vez necesitas crear una cuenta local (no es una cuenta de internet, es solo para este sistema en tu computador):

1. Haz clic en **"Sign up"**
2. Ingresa tu nombre, email (puede ser cualquiera, incluso inventado) y una contraseña
3. Haz clic en **"Create Account"**

> Las veces siguientes solo deberás hacer **"Sign in"** con ese email y contraseña.

### 6.3 Seleccionar el modelo

En la parte superior de la pantalla verás un selector de modelo. Asegúrate de que esté seleccionado uno de los modelos disponibles (el nombre del modelo suele incluir "ENE" o "ENUSC" dependiendo del tema que quieras consultar).

### 6.4 Hacer preguntas

Simplemente escribe tu pregunta en español en el cuadro de texto inferior. Por ejemplo:

- *"¿Cuál fue la tasa de desocupación nacional en 2023?"*
- *"Muéstrame la tasa de ocupación de mujeres en la región de Valparaíso entre 2020 y 2023"*
- *"¿Cómo ha evolucionado la percepción de aumento de la delincuencia a nivel nacional?"*
- *"Compara la victimización de hogares por delitos violentos entre hombres y mujeres en 2022"*

El sistema:
1. Interpreta tu pregunta
2. Genera una consulta SQL automáticamente
3. La ejecuta en la base de datos
4. Te muestra los resultados

### 6.5 Indicadores disponibles

**Empleo (ENE):**
- Tasa de desocupación
- Tasa de ocupación
- Tasa de participación
- Personas en la fuerza de trabajo
- Personas ocupadas / desocupadas
- Población en edad de trabajar

**Delincuencia (ENUSC):**
- Percepción de aumento de la delincuencia en el país
- Victimización de hogares por delitos de mayor connotación social
- Victimización de hogares por delitos violentos
- Victimización de personas por delitos violentos

**Desgloses disponibles:**
- Nacional (total país)
- Por sexo (hombres / mujeres)
- Por región (las 16 regiones de Chile)
- Series temporales anuales y mensuales (según disponibilidad)

---

## 7. Apagar el proyecto

Cuando termines de trabajar, es buena práctica apagar los contenedores para liberar memoria y recursos de tu computador.

---

#### macOS

```bash
make prod-down
```

---

#### Windows

```powershell
docker compose --profile prod down
```

---

Verás que los contenedores se detienen. **Los datos se guardan automáticamente** y estarán disponibles la próxima vez que inicies el proyecto.

---

## 8. Uso diario

Una vez que ya hiciste la primera instalación, el uso diario es muy simple:

### Para iniciar

---

#### macOS

```bash
# 1. Abre la Terminal
# 2. Ve a la carpeta del proyecto
cd ~/proyectos/chatbot/open-webui

# 3. Inicia el proyecto
make prod-up

# 4. Espera ~1 minuto y abre en el navegador
# http://localhost:3030
```

---

#### Windows

```powershell
# 1. Abre PowerShell
# 2. Ve a la carpeta del proyecto
cd C:\Users\tu_nombre\proyectos\chatbot\open-webui

# 3. Inicia el proyecto
docker compose --profile prod up -d

# 4. Espera ~1 minuto y abre en el navegador
# http://localhost:3030
```

---

### Para detener

---

#### macOS

```bash
make prod-down
```

---

#### Windows

```powershell
docker compose --profile prod down
```

---

### Referencia rápida de comandos

| Acción | macOS | Windows |
|--------|-------|---------|
| Iniciar el proyecto | `make prod-up` | `docker compose --profile prod up -d` |
| Detener el proyecto | `make prod-down` | `docker compose --profile prod down` |
| Ver estado | `make status` | `docker ps` |
| Ver logs en vivo | `make prod-logs` | `docker compose --profile prod logs -f` |
| Reiniciar | `make prod-restart` | `docker compose --profile prod down && docker compose --profile prod up -d` |

---

## 9. Solución de problemas

### "No puedo abrir http://localhost:3030"

**Causas posibles y soluciones:**

1. **Docker no está iniciado:** Abre Docker Desktop y espera a que el ícono de la ballena deje de moverse.

2. **Los contenedores no están corriendo:** Verifica con `make status` (macOS) o `docker ps` (Windows). Si no aparecen los tres contenedores, ejecuta el comando de inicio nuevamente.

3. **El chatbot aún está iniciando:** Espera 1-2 minutos más después de iniciar los contenedores.

4. **Otro programa usa el puerto 3030:** En macOS, ejecuta `lsof -i :3030` para ver qué programa lo está usando. En Windows, ejecuta `netstat -ano | findstr :3030`.

---

### "Error: network webui-net not found"

Ejecuta el paso de creación de red:

- macOS: `make network-create`
- Windows: `docker network create webui-net`

---

### "El chatbot responde que no puede hacer la consulta"

Posibles causas:

1. **Clave de API inválida o sin créditos:** Entra a [https://openrouter.ai](https://openrouter.ai) y verifica que tu cuenta tenga créditos y que la clave en el archivo `.env` sea correcta.

2. **El archivo `.env` tiene errores:** Verifica que cada línea tenga el formato `CLAVE=valor` sin espacios alrededor del `=`.

3. **Pregunta demasiado ambigua:** Intenta ser más específico. En vez de "muéstrame datos de empleo", prueba "¿cuál fue la tasa de desocupación nacional en 2022?".

---

### "Docker dice que no hay suficiente memoria"

Docker Desktop necesita al menos 4 GB de RAM asignados. Para cambiar esto:

- **macOS:** Docker Desktop → ícono ballena → Settings → Resources → Memory → Aumenta a 4 GB o más
- **Windows:** Docker Desktop → ícono ballena → Settings → Resources → Advanced → Memory → Aumenta a 4 GB o más

---

### Los contenedores se inician pero uno sale ("Exited")

Revisa los logs para ver el error:

- macOS: `make prod-logs`
- Windows: `docker compose --profile prod logs -f`

Busca líneas con `ERROR` o `error`. Los errores más comunes son:

- **Puerto ocupado:** Otro programa usa el puerto 3031, 5439 u 11435
- **Problema con el archivo .env:** Clave de API con formato incorrecto

---

### Necesito empezar desde cero

Si algo salió muy mal y quieres borrar todo y volver a empezar:

> **Advertencia:** Esto borra todos los datos y configuraciones guardadas. Úsalo solo como último recurso.

---

#### macOS

```bash
make clean-prod
make prod-up
```

---

#### Windows

```powershell
docker compose --profile prod down -v
docker compose --profile prod up -d
```

---

### Contacto y soporte

Si tienes problemas que no están cubiertos aquí, contacta al equipo del proyecto con:
1. Una descripción del problema
2. El mensaje de error exacto (copia y pega desde la terminal)
3. Tu sistema operativo y versión (ej: "macOS Sonoma 14.5" o "Windows 11")

---

*Guía preparada para el Magíster en Estadística Aplicada — Proyecto chatbot indicadores ENE/ENUSC*
