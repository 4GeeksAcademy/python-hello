# StreamLoop — Informe de ajuste del modelo de cancelación

Notebook: [`streamloop_churn_tuning.ipynb`](streamloop_churn_tuning.ipynb)

## 1. Resumen

| Métrica (clase churn, test) | Línea base | Modelo ajustado | Cambio |
|---|---|---|---|
| **F2** (métrica objetivo) | 0.498 | **0.714** | +0.216 |
| Recall | 0.476 | **0.813** | +0.337 |
| Precision | 0.612 | 0.480 | −0.132 |
| F1 | 0.535 | 0.603 | +0.068 |
| Accuracy | 0.781 | 0.716 | −0.065 |

El modelo ajustado detecta a **8 de cada 10** clientes que cancelan, frente a menos de 5 de cada 10 de la línea base. El costo es una precision menor: más clientes reciben una oferta de retención que no necesitaban.

## 2. Proceso

1. **Limpieza mínima:** `TotalCharges` se convirtió a numérico (11 valores vacíos pasaron a `NaN`), se eliminó `customerID` y `Churn` se codificó como 0/1.
2. **Split** 80/20 estratificado (26.5% de churn en ambos conjuntos), hecho antes de cualquier otro paso.
3. **Pipeline** con el preprocesamiento dentro: imputación + escalado (numéricas) e imputación + one-hot (categóricas), más `RandomForestClassifier`.
4. **Línea base** con hiperparámetros por defecto, evaluada en test (1er uso del test set).
5. **`RandomizedSearchCV`** (40 iteraciones, CV estratificado de 5 folds, `n_jobs=-1`) sobre un espacio amplio.
6. **`GridSearchCV`** (180 combinaciones × 5 folds) sobre una región acotada con lo aprendido del paso anterior.
7. **Evaluación final** en test (2º y último uso del test set).

Ninguna búsqueda vio el test set.

## 3. Elección de la métrica: F2

Para StreamLoop, un cliente que cancela sin ser detectado cuesta más que una retención ofrecida sin necesidad. Un falso negativo es más caro que un falso positivo.

- **Accuracy** (valor por defecto) descartada: con ~73% de clientes que no cancelan, predecir siempre "no churn" ya da ~73%.
- **Recall puro** descartado como objetivo: se infla prediciendo "churn" para todos.
- **F2** combina precision y recall pero pesa el recall el doble, que es la prioridad del negocio sin permitir ese truco.

La línea base y el modelo final se comparan con las mismas métricas.

## 4. Búsqueda de hiperparámetros

**Randomized (amplio).** Mejor F2 en CV: 0.722. Los diez mejores candidatos compartían dos rasgos: `class_weight` balanceado (`balanced` o `balanced_subsample`) y `max_depth=5`, que era el valor **más bajo** del rango explorado. `max_features` de 0.3 a 0.5 superó a `sqrt`/`log2`, y `n_estimators` y `min_samples_split` discriminaban poco.

**Grid (focalizado).** Con esa información se exploraron profundidades menores:

| Hiperparámetro | Valores |
|---|---|
| `class_weight` | `balanced`, `balanced_subsample` |
| `max_depth` | 3, 4, 5, 6, 8 |
| `max_features` | 0.3, 0.5, 0.7 |
| `min_samples_leaf` | 1, 3, 5 |
| `n_estimators` | 200, 400 |
| `min_samples_split` | 6 (fijo) |

## 5. Selección del modelo final: promedio vs. estabilidad

Se revisó `cv_results_` completo, no solo el mejor promedio.

| Candidato | F2 medio (CV) | Desv. entre folds | Rango entre folds (máx − mín) |
|---|---|---|---|
| Mayor promedio (`balanced_subsample`, `n_estimators=200`) | 0.7252 | 0.0159 | 0.0425 |
| **Elegido** (`balanced`, `n_estimators=400`) | 0.7245 | **0.0141** | **0.0360** |

La diferencia de promedio es de **0.0007**, mucho menor que la variación entre folds (~0.014–0.016). Con esa diferencia no se puede afirmar que el primero sea realmente mejor, así que se prefirió el candidato con menor desviación y menor rango entre folds.

La regla se aplicó de forma explícita y sin mirar el test: entre los candidatos a ≤ 0.005 del mejor promedio, se elige el de menor desviación. Se implementó con `refit` como función en `GridSearchCV`, de modo que el reentrenamiento lo hace `GridSearchCV` y no se reentrenó `best_estimator_` a mano.

**Hiperparámetros finales:**

```
class_weight      = "balanced"
max_depth         = 3
max_features      = 0.7
min_samples_leaf  = 1
min_samples_split = 6
n_estimators      = 400
```

## 6. Limitaciones y observaciones

- **El óptimo está en el borde del Grid.** `max_depth=3` es el valor más bajo y `max_features=0.7` el más alto de la rejilla. Probablemente haya un poco más de margen fuera de ella; no se exploró para respetar el flujo Randomized → Grid acotado.
- **Hay una meseta.** Muchos candidatos empatan en F2 de CV (≈0.724–0.725). Con `max_depth=3`, `min_samples_leaf` casi no influye. El resultado es robusto a esos parámetros.
- **El costo en precision es real.** Con F2 se aceptó perder precision (0.61 → 0.48) y accuracy (0.78 → 0.72) para ganar recall. Es la decisión coherente con el reto, pero el equipo de retención debe confirmar que el volumen de ofertas adicionales es asumible.
- **Umbral de decisión.** Se usó el umbral por defecto (0.5). Ajustarlo sería otra palanca para mover el balance entre recall y precision, pero queda fuera del alcance de este ajuste.
- **Un solo split.** El resultado en test viene de una única partición; la variación entre folds (~0.014 de desviación) da una idea del orden de magnitud del ruido esperable.
