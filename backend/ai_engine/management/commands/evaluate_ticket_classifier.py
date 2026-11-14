from django.core.management.base import BaseCommand

from ai_engine.evaluation import evaluate_classifier


class Command(BaseCommand):
    help = 'Evaluate the ticket category classifier with a stratified holdout.'

    def handle(self, *args, **options):
        metrics = evaluate_classifier()
        self.stdout.write(f"Samples: {metrics['sample_count']}")
        self.stdout.write(f"Class counts: {metrics['class_counts']}")
        self.stdout.write(f"Duplicate rows: {metrics['duplicate_count']}")
        self.stdout.write(
            f"Train/test overlap: {metrics['train_test_overlap_count']}"
        )
        self.stdout.write(f"Accuracy: {metrics['accuracy']:.4f}")
        self.stdout.write(f"Macro precision: {metrics['precision']:.4f}")
        self.stdout.write(f"Macro recall: {metrics['recall']:.4f}")
        self.stdout.write(f"Macro F1: {metrics['f1']:.4f}")
        self.stdout.write("Per-class metrics:")
        for category, values in metrics['per_class'].items():
            self.stdout.write(
                f"  {category}: precision={values['precision']:.4f}, "
                f"recall={values['recall']:.4f}, f1={values['f1']:.4f}"
            )
        self.stdout.write(
            f"Confusion matrix ({', '.join(metrics['labels'])}): "
            f"{metrics['confusion_matrix']}"
        )
