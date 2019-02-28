"""Relevance Vector Machine classes for regression and classification.

Tom Bolton
27/02/2019
thomasmichaelbolton@gmail.com

Adapted from JamesRitchie/scikit-rvm repository. The main differences between
original code and this implementation are the following:

- Only regression is considered (classification is ignored).
- Kernel transformations are removed, such that each column/feature in X is 
  assumed to be a basis function.
- A list of basis function labels is supplied to the model, and after fitting
  the sparse representation of the basis functions is printed.
- When verbose is switched on, the model communicates which basis functions
  are being pruned from the data.

Without the application of a kernel, this model solves the following
(linear) Bayesian regression problem

               y = w.phi
               
where an individual prior is assigned to each regression weight in w. The
hyperparameters of said hyperpriors are found through type-II maximum 
likelihood (i.e. the evidence approximation). The type-II maximum likelihood
calculation is conducted iteratively.

"""
import numpy as np

from scipy.optimize import minimize
from scipy.special import expit
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_X_y


class BaseRVM(BaseEstimator):

    """Base Relevance Vector Machine class.

    Implementation of Mike Tipping's Relevance Vector Machine using the
    scikit-learn API. Add a posterior over weights method and a predict
    in subclass to use for classification or regression.
    """

    def __init__(
        self,
        n_iter=3000,
        tol=1e-3,
        alpha=1e-6,
        threshold_alpha=1e9,
        beta=1.e-6,
        beta_fixed=False,
        bias_used=True,
        verbose=True,
        verb_freq=10,
    ):
        """Copy params to object properties, no validation."""
        self.n_iter = n_iter
        self.tol = tol
        self.alpha = alpha
        self.threshold_alpha = threshold_alpha
        self.beta = beta
        self.beta_fixed = beta_fixed
        self.bias_used = bias_used
        self.verbose = verbose
        self.verb_freq = verb_freq

    def get_params(self, deep=True):
        """Return parameters as a dictionary."""
        params = {
            'n_iter': self.n_iter,
            'tol': self.tol,
            'alpha': self.alpha,
            'threshold_alpha': self.threshold_alpha,
            'beta': self.beta,
            'beta_fixed': self.beta_fixed,
            'bias_used': self.bias_used,
            'verbose': self.verbose
        }
        return params

    def set_params(self, **parameters):
        """Set parameters using kwargs."""
        for parameter, value in parameters.items():
            setattr(self, parameter, value)
        return self

    def _prune(self):
        """Remove basis functions based on alpha values.
        
        As alpha becomes very large, the corresponding 
        weight of the basis function tends to zero.
        """
        keep_alpha = self.alpha_ < self.threshold_alpha

        # check if we are chucking away all basis functions
        if not np.any(keep_alpha):
            keep_alpha[0] = True
            if self.bias_used:
                keep_alpha[-1] = True

        if self.bias_used:
            if not keep_alpha[-1]:
                self.bias_used = False
            self.relevance_ = self.relevance_[keep_alpha[:-1]]
        else:
            self.relevance_ = self.relevance_[keep_alpha]

        self.alpha_ = self.alpha_[keep_alpha]
        self.alpha_old = self.alpha_old[keep_alpha]
        self.gamma = self.gamma[keep_alpha]
        self.phi = self.phi[:, keep_alpha]
        self.sigma_ = self.sigma_[np.ix_(keep_alpha, keep_alpha)]
        self.m_ = self.m_[keep_alpha]

    def fit(self, X, y, X_labels ):
        """Fit the RVR to the training data.
        
        X: 2D array where each row is an observation and 
           each column represents a basis function.
           
        y: 1D array of targets
        
        X_labels: A list of strings providing a description
                  of each basis function e.g. d2u/dx2.
        
        """
        X, y = check_X_y(X, y)

        n_samples, n_features = X.shape

        self.phi = X
        self.labels = X_labels

        n_basis_functions = self.phi.shape[1]

        self.relevance_ = X
        self.y = y

        self.alpha_ = self.alpha * np.ones(n_basis_functions)
        self.beta_ = self.beta

        self.m_ = np.zeros(n_basis_functions)

        self.alpha_old = self.alpha_

        for i in range(self.n_iter):
            self._posterior()

            self.gamma = 1 - self.alpha_*np.diag(self.sigma_)
            self.alpha_ = self.gamma/(self.m_ ** 2)

            if not self.beta_fixed:
                self.beta_ = (n_samples - np.sum(self.gamma))/(
                    np.sum((y - np.dot(self.phi, self.m_)) ** 2))

            self._prune()

            if self.verbose and ( (i+1) % self.verb_freq == 0 ):
                print "Fit @ iteration {}:".format(i) 
                print "--Alpha {}".format( self.alpha_ )
                print "--Beta {}".format( self.beta_ ) 
                print "--Gamma {}".format( self.gamma ) 
                print "--m {}".format( self.m_ ) 
                print "--Relevance Vectors {}\n".format( self.relevance_.shape[0] ) 

            delta = np.amax(np.absolute(self.alpha_ - self.alpha_old))

            if delta < self.tol and i > 1:
                print "Fit: delta < tol @ iteration {}, finished.".format(i)
                break

            self.alpha_old = self.alpha_

        if self.bias_used:
            self.bias = self.m_[-1]
        else:
            self.bias = None

        return self


class RVR(BaseRVM, RegressorMixin):

    """Relevance Vector Machine Regression.

    Implementation of Mike Tipping's Relevance Vector Machine for regression
    using the scikit-learn API.
    """

    def _posterior(self):
        """Compute the posterior distriubtion over weights."""
        i_s = np.diag(self.alpha_) + self.beta_ * np.dot(self.phi.T, self.phi)
        self.sigma_ = np.linalg.inv(i_s)
        self.m_ = self.beta_ * np.dot(self.sigma_, np.dot(self.phi.T, self.y))

    def predict(self, X, eval_MSE=False):
        """Evaluate the RVR model at x."""
        phi = X

        y = np.dot(phi, self.m_)

        if eval_MSE:
            MSE = (1/self.beta_) + np.dot(phi, np.dot(self.sigma_, phi.T))
            return y, MSE[:, 0]
        else:
            return y


