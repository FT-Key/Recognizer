# web/public

Archivos estáticos que Vite copia tal cual a `dist/`.

## Foto de "Sobre mí"

La página *Sobre mí* carga el retrato desde **`/me.webp`**:

```
web/public/me.webp
```

Si el archivo no existe, se muestra un marcador de posición con las instrucciones
(no rompe nada). Para cambiarlo, reemplazá `me.webp` o ajustá `PHOTO_SRC` en
`src/pages/AboutPage.jsx`.

Recomendado: imagen cuadrada, mínimo 400×400 px.
