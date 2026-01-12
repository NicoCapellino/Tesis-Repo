# Guía de Gestión de Datos con DVC

Este proyecto utiliza **DVC (Data Version Control)** para gestionar los datasets grandes que no pueden subirse a GitHub. DVC funciona "encima" de Git, almacenando punteros de texto ligeros en el repositorio mientras los archivos pesados se guardan en Google Drive.

## 1. Configuración Inicial (Para nuevos colaboradores)

Si acabas de clonar el repositorio, sigue estos pasos:

1.  **Instala los requisitos:**
    Asegúrate de tener Python instalado y ejecuta:
    ```powershell
    pip install "dvc[gdrive]"
    ```

2.  **Descarga los datos:**
    Trae los archivos pesados desde el almacenamiento remoto a tu equipo local:
    ```powershell
    dvc pull
    ```
    *Nota: La primera vez se abrirá una ventana en tu navegador para autenticarte con tu cuenta de Google. Usa la cuenta que tiene acceso a la carpeta compartida.*

---

## 2. Flujo de Trabajo Diario

### Agregar o Actualizar un Dataset

Cuando generes un nuevo archivo de datos (ej. `notebooks/data/clean_data.csv`) o modifiques uno existente:

1.  **Rastrea el archivo con DVC:**
    ```powershell
    dvc add notebooks/data/clean_data.csv
    ```
    Esto creará un archivo `.dvc` (ej. `notebooks/data/clean_data.csv.dvc`) y actualizará el `.gitignore` para ignorar el archivo pesado original.

2.  **Sube los cambios a la nube:**
    ```powershell
    dvc push
    ```

3.  **Guarda los punteros en Git:**
    Sube los archivos creados por DVC al repositorio de código:
    ```powershell
    git add notebooks/data/clean_data.csv.dvc notebooks/data/.gitignore
    git commit -m "Actualizar dataset clean_data"
    git push
    ```

### Obtener los cambios de tu compañero

1.  **Baja el código más reciente:**
    ```powershell
    git pull
    ```

2.  **Sincroniza los datos:**
    Si Git trajo nuevos archivos `.dvc`, actualiza tus datos locales:
    ```powershell
    dvc pull
    ```

---

## 3. Configuración del Remote (Solo administradores)

El almacenamiento remoto ya está configurado en `.dvc/config`. Si necesitas cambiarlo o reconfigurarlo:

```powershell
# Configurar Google Drive como storage
dvc remote add -d storage gdrive://TU_FOLDER_ID

# Guardar la configuración
git add .dvc/config
git commit -m "Configurar DVC remote"
```

## Solución de Problemas Comunes

*   **Error de autenticación:** Si `dvc push/pull` falla por permisos, intenta borrar el archivo de credenciales locales en `.dvc/tmp/gdrive-user-credentials.json` y autentícate de nuevo.
*   **Git ignora mis archivos .dvc:** Asegúrate de que las carpetas de datos (ej. `data/`) NO estén en el `.gitignore` raíz. DVC gestiona sus propios `.gitignore` dentro de esas carpetas.
