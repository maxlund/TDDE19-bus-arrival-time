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
from sklearn.preprocessing import StandardScaler

class GP(NamedTuple):
    model: GPRegression
    X: np.ndarray
    Y: np.ndarray
    X_scaler: StandardScaler
    Y_scaler: StandardScaler
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
    """
    Wraps the GPy predict function. Scales the data before predicting.
    """
    X_scaled = gp.X_scaler.transform(X)
    Y_scaled, var = gp.model.predict(X_scaled)
    return (gp.Y_scaler.inverse_transform(Y_scaled), var)

def plot(gp: GP):
    gp.model.plot()

def set_params(gp: GP, params: np.ndarray):
    gp.model[:] = params
    gp.model.update_model(True)
    return gp

def build_synch(X: np.ndarray,
                Y: np.ndarray,
                version: str,
                route_n: int,
                seg_n: int) -> GP:

    return build(X, Y, 'synch-' + str(version), route_n, 0, seg_n)

def build(X: np.ndarray,
          Y: np.ndarray,
          name: int,
          route_n: int,
          traj_n: int,
          seg_n: int) -> GP:
    """
    Creates a wrapper data type arounnd a GPy regression model.
    This is done to enable saving of more information together with the models when
    writing to file. Also scales the data. The results are terrible without scaling it.
    """
    X_scaler = StandardScaler()
    Y_scaler = StandardScaler()
    X_scaler.fit(X)
    Y_scaler.fit(Y)
    k = GPy.kern.RBF(input_dim=X.shape[1], ARD=False)
    model = GPy.models.GPRegression(X_scaler.transform(X), Y_scaler.transform(Y), k)
    return GP(model, X, Y, X_scaler, Y_scaler, name, route_n, traj_n, seg_n)

# def scale_latlon(X: np.ndarray):
#     lat_max = np.amax(X[:, 0])
#     lon_max = np.amax(X[:, 1])
#     return X/max([lat_max, lon_max])




## PRIORS ##

def set_kern_ls_prior(gp: GP, prior):
    gp.model.kern.lengthscale.set_prior(prior)

def set_kern_var_prior(gp: GP, prior):
    gp.model.kern.variance.set_prior(prior)

def set_lik_var_prior(gp: GP, prior):
    gp.model.likelihood.variance.set_prior(gp, prior)

def gamma_prior(mean: float, var: float):
    return GPy.priors.Gamma.from_EV(mean, var)






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
    m = re.match(r'./gps/*/(\d+).(\d+).(\d+).*', file_path)
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
    params_path = path + __gp_model_file(gp.route_n, gp.traj_n, gp.seg_n)
    save_params(gp.model.param_array, params_path)

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

def load_params(path):
    return np.load(path)

def save_params(params, path):
    return np.save(path, params)

def load_synch(route_n: int, seg_n: int, version: str) -> GP:
    return load('synch-' + str(version), route_n, 0, seg_n)

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
    params = load_params(model_path)
    gp = build(X, Y, name, route_n, traj_n, seg_n)
    return set_params(gp, params)

def load_trajs(name: str, route_n: int, seg_n: int) -> List[GP]:
    """
    Loads all GPs with the given name, trained on trajectories for provided route and segment.
    """
    file_reg = __gp_path(name) + str(route_n) + '.*.' + str(seg_n)
    data_reg = file_reg  + '.pkl'
    param_reg = file_reg + '.npy'
    datas = [load_data(p) for p in glob.glob(data_reg)]
    params = [load_params(p) for p in glob.glob(param_reg)]
    traj_ns = re.findall(r'\d+.(\d+).\d+.pkl', ''.join(glob.glob(data_reg)))
    def from_params(data, params, traj_n):
        X = data[0]
        Y = data[1]
        model = build(X, Y, name, route_n, traj_n, seg_n)
        return set_params(model, params)
    return [from_params(d, p, t) for d, p, t in zip(datas, params, traj_ns)]

#    spara arrival time och modellen bara
    # Find all .npy files in name save dir
#    params = [load_gp(path) for path in file_paths]
 #   return {r: {t: {s: p for _, _, s, p in params}
  #              for _, t, _, _ in params}
   #         for r, _, _, _ in params}
