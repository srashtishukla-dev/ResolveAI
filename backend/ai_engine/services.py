from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ai_engine.ml_data import TRAINING_EXAMPLES, TRAINING_LABELS


CATEGORY_ORDER = ('TECHNICAL', 'BILLING', 'ACCOUNT', 'GENERAL')

MODEL_PATH = (
    Path(__file__).resolve().parent.parent / 'ml_models' /
    'ticket_category_classifier.joblib'
)


class ModelNotTrainedError(FileNotFoundError):
    """Raised when the trained category classifier artifact is unavailable."""


def build_training_pipeline():
    texts = [f'{title}. {description}' for title, description in TRAINING_EXAMPLES]
    pipeline = Pipeline([
        (
            'tfidf',
            TfidfVectorizer(
                analyzer='char_wb',
                ngram_range=(3, 5),
                lowercase=True,
            ),
        ),
        ('classifier', LogisticRegression(max_iter=1000, random_state=42)),
    ])
    pipeline.fit(texts, TRAINING_LABELS)
    return pipeline


def train_classifier(output_path=MODEL_PATH):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline = build_training_pipeline()
    joblib.dump(pipeline, output_path)
    load_classifier.cache_clear()
    return output_path


@lru_cache(maxsize=1)
def load_classifier():
    if not MODEL_PATH.is_file():
        raise ModelNotTrainedError(
            'The ticket category model has not been trained. '
            'Run "python manage.py train_ticket_classifier".'
        )
    return joblib.load(MODEL_PATH)


def classify_ticket(title, description):
    classifier = load_classifier()
    text = f'{title.strip()}. {description.strip()}'

    probabilities = classifier.predict_proba([text])[0]
    predicted_index = probabilities.argmax()

    prediction = classifier.classes_[predicted_index]
    confidence = float(probabilities[predicted_index])

    return prediction, max(0.0, min(1.0, confidence))