"""Run once, at Docker image BUILD time (see the Dockerfile's builder stage). (Provided - do not edit.)

This script itself never ships into the runtime image - only the ``model/model.joblib`` it writes does
(the runtime stage's Dockerfile does ``COPY --from=builder /build/model ./model`` and nothing else from
the builder). That keeps scikit-learn's training-only footprint (and this file) out of the image you
actually serve traffic from, while the serving image still needs scikit-learn+joblib installed to be
able to *load* and call the pickled model at request time.
"""

from pathlib import Path

from app.model import MODEL_PATH, save, train

if __name__ == "__main__":
    classifier, target_names = train()
    out = Path("model") / MODEL_PATH.name
    save(classifier, target_names, out)
    print(f"trained model, wrote {out} ({out.stat().st_size} bytes), classes={target_names}")
