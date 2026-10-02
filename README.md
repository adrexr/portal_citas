# ClinicaFlow

ClinicaFlow es un tablero de coordinación de capacidad clínica. Convierte cuatro variables operativas agregadas —citas programadas, personal de turno, duración de la cita y consultorios— en un plan explicable para el turno.

No usa clima, servicios externos ni datos de pacientes. No diagnostica, prioriza ni evalúa personas.

## Ejecutar

Requiere Python 3.10 o posterior.

```powershell
python main.py
```

Abre `http://127.0.0.1:8000`. Presiona `Ctrl+C` para detener el servidor.

## API

`GET /api/analysis` recibe `service`, `appointments`, `clinicians`, `minutes` y `rooms`. Retorna la capacidad total, ocupación estimada, citas sin capacidad y el refuerzo sugerido.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Arquitectura

```text
climastock/analyzer.py  Motor determinista de capacidad por turno
climastock/web.py       Servidor local y API
api/analysis.py         Función compatible con Vercel
index.html              Tablero operativo
tests/test_climastock.py Pruebas de reglas y contrato API
```
