"""Convenience functions for GPs using GPy."""

import os
import glob
import re
import pickle
from typing import NamedTuple, List, Dict
import numpy as np
import pandas as pd

import GPy
from GPy.models import GPRegression
from sklearn.preprocessing import scale

class GP(NamedTuple):
    model: GPRegression
    X: np.ndarray
    Y: np.ndarray
    name: str
    route_n: int
    traj_n: int
    seg_n: int

## FUNCTIONS ACTING ON GP ##

def loglik(gp: GP):
    return gp.model.log_likelihood()

def train(gp: GP, n_restarts: int):
    gp.model.optimize_restarts(n_restarts)

def predict(gp: GP, X: np.ndarray) -> np.ndarray:
    return gp.model.predict(scale(X))

def plot(gp: GP):
    gp.model.plot()

def set_params(gp: GP, params: np.ndarray):
    gp.model[:] = params
    gp.model.update_model(True)
    return gp

def __make_model(X: np.ndarray,
                 Y: np.ndarray,
                 name: str,
                 route_n: int,
                 traj_n: int,
                 seg_n: int):
    """
    Creates our own data type which wraps GPys regression model.
    This is done to enable saving of more information together with the models when
    writing to file.
    """
    model = GPy.models.GPRegression(X, Y,
        GPy.kern.RBF(input_dim=X.shape[1],
                     variance=1.,
                     lengthscale=1.))
    return GP(model, X, Y, name, route_n, traj_n, seg_n)

def build_synch(data: pd.DataFrame,
                X: List[str],
                Y: List[str],
                seg_n: int) -> GP:
    return build(data, X, Y, 'synch', 0, 0, seg_n)

def build(data: pd.DataFrame,
          X: List[str],
          Y: List[str],
          name: int,
          route_n: int,
          traj_n: int,
          seg_n: int) -> GP:
    """Wraps the model creation with a nices interface against pandas tables."""
    x_vals = scale(data[X].values)
    y_vals = data[Y].values
    return __make_model(x_vals, y_vals, name, route_n, traj_n, seg_n)

## SAVE AND LOAD STUFF ##

def __gp_path(name: str) -> str:
    gp_dir = r'./gps'
    return gp_dir + '/' + name + '/'

def __gp_file_name(route_n: int, traj_n: int, seg_n: int) -> str:
    return str(int(route_n)) \
        + '.' + str(int(traj_n)) \
        + '.' + str(int(seg_n))

def __gp_model_file(route_n: int, traj_n: int, seg_n: int) -> str:
    return __gp_file_name(route_n, traj_n, seg_n) + '.npy'

def __gp_data_file(route_n: int, traj_n: int, seg_n: int) -> str:
    return __gp_file_name(route_n, traj_n, seg_n) + '.pkl'

def __gp_file_info(file_path: str) -> (int, int, int):
    m = re.match(r'./gps/pred-v1\\(\d+).(\d+).(\d+).*', file_path)
    return m.group(1), m.group(2), m.group(3)

def save(gp: GP) -> None:
    """
    Saves the model. The files that it is saved to is generated by its internal fields.
    Should a new model with the same name, route, trajectory and segment be provided
    the old one will be over written.
    KNOWN BUG: The priors of the model disappear when stored.
    """
    path = __gp_path(gp.name)
    if not os.path.exists(path):
        os.makedirs(path)

    # The GPy model parameters are written to one file
    model_path = path + __gp_model_file(gp.route_n, gp.traj_n, gp.seg_n)
    np.save(model_path, gp.model.param_array)

    # The values of the rest of the object is written to another
    data_path = path + __gp_data_file(gp.route_n, gp.traj_n, gp.seg_n)
    data = (gp.X, gp.Y)
    save_data(data, data_path)

def save_data(data, path):    
    with open(path, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_data(path):
    with open(path, 'rb') as handle:
        X, Y = pickle.load(handle)
    return X, Y

def load_synch(traj_n: int) -> GP:
    return load('synch', 0, 0, traj_n)

def load(name: str,
         route_n: int,
         traj_n: int,
         seg_n: int) -> GP:
    """
    Loads a model that has previously been saved for the provided name, route, traj, seg.
    KNOWN BUG: The priors of the model disappear when stored.
    """
    path = __gp_path(name)
    data_path  = path + __gp_data_file(route_n, traj_n, seg_n)
    model_path = path + __gp_model_file(route_n, traj_n, seg_n)
    X, Y = load_data(data_path)
    params = np.load(model_path)
    gp = __make_model(X, Y, name, route_n, traj_n, seg_n)
    return set_params(gp, params)

def load_all_params(name: str) -> Dict[int, Dict[int, Dict[int, np.ndarray]]]:
    """
    Returns a LUT indexed by route, traj, seg which contains parameters
    for all saved GPs of the provided name.
    """

#    spara arrival time och modellen bara
    # Find all .npy files in name save dir
    file_paths = [f for f in glob.glob(__gp_path(name) + '*.npy')]
    return [load_gp(path) for path in file_paths]
#    params = [load_gp(path) for path in file_paths]
 #   return {r: {t: {s: p for _, _, s, p in params}
  #              for _, t, _, _ in params}
   #         for r, _, _, _ in params}
