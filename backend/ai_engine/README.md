# Ticket category classifier

The classifier uses 120 synthetic support-ticket examples, evenly divided
between `TECHNICAL`, `BILLING`, `ACCOUNT`, and `GENERAL`. It combines the
ticket title and description, transforms the text with character n-grams using
`TfidfVectorizer`, and
predicts a category with `LogisticRegression` in a scikit-learn `Pipeline`.

The examples are artificial and do not establish production accuracy or
represent real customer data.

Evaluate the model with a reproducible stratified 75/25 train/test split:

```cmd
venv\Scripts\python.exe manage.py evaluate_ticket_classifier
```

The evaluation reports accuracy, macro precision, macro recall, macro F1,
per-class metrics, a confusion matrix, class counts, duplicate rows, and
train/test text overlap. The evaluation is a holdout estimate on synthetic
data, not evidence of production-level accuracy.

Train or regenerate the local joblib artifact from the backend directory:

```cmd
venv\Scripts\python.exe manage.py train_ticket_classifier
```

The generated artifact is stored at `backend\ml_models\ticket_category_classifier.joblib`
and is excluded from Git. The API loads it once per process and returns a
503 response until the training command has been run.
