import sklearn
import numpy as np


def l2_normalize(EV: np.ndarray, **kwargs):
    # EV /= np.linalg.norm(EV, axis=1, keepdims=True)
    
    scaler = sklearn.preprocessing.Normalizer(norm='l2')     # Use sklearn for saftey
    EV = scaler.fit_transform(EV)
    return EV