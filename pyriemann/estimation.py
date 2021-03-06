"""Estimation of covariance matrices."""
import numpy

from .spatialfilters import Xdawn
from .utils.covariance import covariances, covariances_EP, cospectrum
from sklearn.base import BaseEstimator, TransformerMixin


def _nextpow2(i):
    """Find next power of 2."""
    n = 1
    while n < i:
        n *= 2
    return n


class Covariances(BaseEstimator, TransformerMixin):

    """Estimation of covariance matrix.

    Perform a simple covariance matrix estimation for each givent trial.

    Parameters
    ----------
    estimator : string (default: 'scm')
        covariance matrix estimator. For regularization consider 'lwf' or 'oas'
        For a complete list of estimator, see `utils.covariances`.

    See Also
    --------
    ERPCovariances
    XdawnCovariances
    CospCovariances
    """

    def __init__(self, estimator='scm'):
        """Init."""
        self.estimator = estimator

    def fit(self, X, y=None):
        """Fit.

        Do nothing. For compatibility purpose.

        Parameters
        ----------
        X : ndarray, shape (n_trials, n_channels, n_samples)
            ndarray of trials.
        y : ndarray shape (n_trials, 1)
            labels corresponding to each trial, not used.

        Returns
        -------
        self : Covariances instance
            The Covariances instance.
        """
        return self

    def transform(self, X):
        """Estimate covariance matrices.

        Parameters
        ----------
        X : ndarray, shape (n_trials, n_channels, n_samples)
            ndarray of trials.

        Returns
        -------
        covmats : ndarray, shape (n_trials, n_channels, n_channels)
            ndarray of covariance matrices for each trials.
        """
        covmats = covariances(X, estimator=self.estimator)
        return covmats


class ERPCovariances(BaseEstimator, TransformerMixin):

    """Estimate special form covariance matrix for ERP.

    Estimation of special form covariance matrix dedicated to ERP processing.
    For each class, a prototyped response is obtained by average across trial :

    .. math::
        \mathbf{P} = \\frac{1}{N} \sum_i^N \mathbf{X}_i

    and a super trial is build using the concatenation of P and the trial X :

    .. math::
        \mathbf{\\tilde{X}}_i =  \left[
                                 \\begin{array}{c}
                                 \mathbf{P} \\\\
                                 \mathbf{X}_i
                                 \end{array}
                                 \\right]

    This super trial :math:`\mathbf{\\tilde{X}}_i` will be used for covariance
    estimation.
    This allows to take into account the spatial structure of the signal, as
    described in [1].

    Parameters
    ----------
    classes : list of int | None (default None)
        list of classes to take into account for prototype estimation.
        If None (default), all classes will be accounted.
    estimator : string (default: 'scm')
        covariance matrix estimator. For regularization consider 'lwf' or 'oas'
        For a complete list of estimator, see `utils.covariances`.
    svd : int | None (default None)
        if not none, the prototype responses will be reduce using a svd using
        the number of components passed in svd.

    See Also
    --------
    Covariances
    XdawnCovariances
    CospCovariances

    References
    ----------
    [1] A. Barachant, M. Congedo ,"A Plug&Play P300 BCI Using Information
    Geometry", arXiv:1409.0107, 2014.

    [2] M. Congedo, A. Barachant, A. Andreev ,"A New generation of
    Brain-Computer Interface Based on Riemannian Geometry", arXiv: 1310.8115.
    2013.

    [3] A. Barachant, M. Congedo, G. Van Veen, C. Jutten, "Classification de
    potentiels evoques P300 par geometrie riemannienne pour les interfaces
    cerveau-machine EEG", 24eme colloque GRETSI, 2013.
    """

    def __init__(self, classes=None, estimator='scm', svd=None):
        """Init."""
        self.classes = classes
        self.estimator = estimator
        self.svd = svd

        if svd is not None:
            if not isinstance(svd, int):
                raise TypeError('svd must be None or int')

    def fit(self, X, y):
        """Fit.

        Estimate the Prototyped response for each classes.

        Parameters
        ----------
        X : ndarray, shape (n_trials, n_channels, n_samples)
            ndarray of trials.
        y : ndarray shape (n_trials, 1)
            labels corresponding to each trial.

        Returns
        -------
        self : ERPCovariances instance
            The ERPCovariances instance.
        """
        if self.classes is not None:
            classes = self.classes
        else:
            classes = numpy.unique(y)

        self.P = []
        for c in classes:
            # Prototyped responce for each class
            P = numpy.mean(X[y == c, :, :], axis=0)

            # Apply svd if requested
            if self.svd is not None:
                U, s, V = numpy.linalg.svd(P)
                P = numpy.dot(U[:, 0:self.svd].T, P)

            self.P.append(P)

        self.P = numpy.concatenate(self.P, axis=0)
        return self

    def transform(self, X):
        """Estimate special form covariance matrices.

        Parameters
        ----------
        X : ndarray, shape (n_trials, n_channels, n_samples)
            ndarray of trials.

        Returns
        -------
        covmats : ndarray, shape (n_trials, n_c, n_c)
            ndarray of covariance matrices for each trials, with n_c the size
            of covmats equal to n_channels * (n_classes + 1) in case svd is
            None and equal to n_channels + n_classes * svd otherwise.
        """
        covmats = covariances_EP(X, self.P, estimator=self.estimator)
        return covmats


class XdawnCovariances(BaseEstimator, TransformerMixin):

    """
    Compute xdawn, project the signal and compute the covariances

    """

    def __init__(self, nfilter=4, applyfilters=True, classes=None,
                 estimator='scm'):
        """Init."""
        self.Xd = Xdawn(nfilter=nfilter, classes=classes)
        self.applyfilters = applyfilters
        self.estimator = estimator

    def fit(self, X, y):
        self.Xd.fit(X, y)
        return self

    def transform(self, X):
        if self.applyfilters:
            X = self.Xd.transform(X)

        covmats = covariances_EP(X, self.Xd.evokeds_, estimator=self.estimator)
        return covmats

    def fit_transform(self, X, y):
        self.fit(X, y)
        return self.transform(X)

###############################################################################


class CospCovariances(BaseEstimator, TransformerMixin):

    """
    compute the cospectral covariance matrices

    """

    def __init__(self, window=128, overlap=0.75, fmin=None, fmax=None, fs=None,
                 phase_correction=False):
        """Init."""
        self._window = _nextpow2(window)
        self._overlap = overlap
        self._fmin = fmin
        self._fmax = fmax
        self._fs = fs

        self._phase_corr = phase_correction

    def fit(self, X, y=None):
        return self

    def transform(self, X):

        Nt, Ne, _ = X.shape
        out = []

        for i in range(Nt):
            S = cospectrum(X[i], window=self._window, overlap=self._overlap,
                           fmin=self._fmin, fmax=self._fmax, fs=self._fs)
            out.append(S.real)

        return numpy.array(out)

    def fit_transform(self, X, y=None):
        return self.transform(X)
