from collections import Counter

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split

from ai_engine.services import CATEGORY_ORDER, build_training_pipeline
from ai_engine.ml_data import TRAINING_EXAMPLES, TRAINING_LABELS


def evaluate_classifier(test_size=0.25, random_state=42):
    texts = [f'{title}. {description}' for title, description in TRAINING_EXAMPLES]
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        TRAINING_LABELS,
        test_size=test_size,
        stratify=TRAINING_LABELS,
        random_state=random_state,
    )
    pipeline = build_training_pipeline()
    pipeline.fit(train_texts, train_labels)
    predictions = pipeline.predict(test_texts)
    report = classification_report(
        test_labels,
        predictions,
        labels=CATEGORY_ORDER,
        output_dict=True,
        zero_division=0,
    )
    return {
        'sample_count': len(texts),
        'class_counts': dict(Counter(TRAINING_LABELS)),
        'duplicate_count': len(texts) - len(set(texts)),
        'train_test_overlap_count': len(set(train_texts) & set(test_texts)),
        'accuracy': accuracy_score(test_labels, predictions),
        'precision': report['macro avg']['precision'],
        'recall': report['macro avg']['recall'],
        'f1': report['macro avg']['f1-score'],
        'per_class': {
            category: {
                'precision': report[category]['precision'],
                'recall': report[category]['recall'],
                'f1': report[category]['f1-score'],
            }
            for category in CATEGORY_ORDER
        },
        'confusion_matrix': confusion_matrix(
            test_labels,
            predictions,
            labels=CATEGORY_ORDER,
        ).tolist(),
        'labels': list(CATEGORY_ORDER),
    }
