#!/usr/bin/env python3
# -*- coding: utf-8 -*
from __future__ import division, print_function, absolute_import
from shl_scripts.shl_encode import sparse_encode
import time
import numpy as np

# SparseHebbianLearning
class SparseHebbianLearning:
    """Sparse Hebbian learning

    Finds a dictionary (a set of atoms) that can best be used to represent data
    using a sparse code.

    Parameters
    ----------

    n_dictionary : int,
        Number of dictionary elements to extract

    eta : float
        Gives the learning parameter for the homeostatic gain.

    n_iter : int,
        total number of iterations to perform

    eta_homeo : float
        Gives the learning parameter for the homeostatic gain.

    alpha_homeo : float
        Gives the smoothing exponent  for the homeostatic gain
        If equal to 1 the homeostatic learning rule learns a linear relation to
        variance.

    dictionary : array of shape (n_dictionary, n_pixels),
        initial value of the dictionary for warm restart scenarios
        Use ``None`` for a new learning.

    fit_algorithm : {'mp', 'lars', 'cd'}
        see sparse_encode

    batch_size : int,
        The number of samples to take in each batch.

    l0_sparseness : int, ``0.1 * n_pixels`` by default
        Number of nonzero coefficients to target in each column of the
        solution. This is only used by `algorithm='lars'`, `algorithm='mp'`  and
        `algorithm='omp'`.

    fit_tol : float, 1. by default
        If `algorithm='lasso_lars'` or `algorithm='lasso_cd'`, `fit_tol` is the
        penalty applied to the L1 norm.
        If `algorithm='threshold'`, `fit_tol` is the absolute value of the
        threshold below which coefficients will be squashed to zero.
        If `algorithm='mp'` or `algorithm='omp'`, `fit_tol` is the tolerance
        parameter: the value of the reconstruction error targeted. In this case,
        it overrides `l0_sparseness`.

    verbose :
        degree of verbosity of the printed output

    Attributes
    ----------
    dictionary : array, [n_dictionary, n_pixels]
        dictionary extracted from the data


    Notes
    -----
    **References:**

    Olshausen BA, Field DJ (1996).
    Emergence of simple-cell receptive field properties by learning a sparse code for natural images.
    Nature, 381: 607-609. (http://redwood.berkeley.edu/bruno/papers/nature-paper.pdf)

    Olshausen BA, Field DJ (1997)
    Sparse Coding with an Overcomplete Basis Set: A Strategy Employed by V1?
    Vision Research, 37: 3311-3325.   (http://redwood.berkeley.edu/bruno/papers/VR.pdf)

    See also
    --------
    http://scikit-learn.org/stable/auto_examples/decomposition/plot_image_denoising.html

    """
    def __init__(self, fit_algorithm, dictionary=None, precision=None, P_cum=None, n_dictionary=None,
                 eta=0.02, n_iter=40000,
                 eta_homeo=0.001, alpha_homeo=0.02,
                 batch_size=100,
                 l0_sparseness=None, fit_tol=None, do_precision=None, do_mask=True,
                 nb_quant=32, C=0., do_sym=True,
                 record_each=200, verbose=False, random_state=None,
                 do_HAP=False):
        self.eta = eta
        self.dictionary = dictionary
        self.precision = precision
        self.n_dictionary = n_dictionary
        self.n_iter = n_iter
        self.eta_homeo = eta_homeo
        self.alpha_homeo = alpha_homeo
        self.fit_algorithm = fit_algorithm
        self.nb_quant = nb_quant
        self.C = C
        self.do_sym = do_sym
        self.batch_size = batch_size
        self.l0_sparseness = l0_sparseness
        self.fit_tol = fit_tol
        self.do_precision = do_precision
        self.do_mask = do_mask
        self.record_each = record_each
        self.verbose = verbose
        self.random_state = random_state
        self.P_cum  = P_cum
        self.do_HAP = do_HAP

    def fit(self, X, y=None):
        """Fit the model from data in X.

        Parameters
        ----------
        X: array-like, shape (n_samples, n_pixels)
            Training vector, where n_samples in the number of samples
            and n_pixels is the number of features.

        Returns
        -------
        self : object
            Returns the instance itself.
        """

        return_fn = dict_learning(X, self.dictionary, self.precision, self.P_cum,
                                  self.eta, self.n_dictionary, self.l0_sparseness,
                                  n_iter=self.n_iter, eta_homeo=self.eta_homeo, alpha_homeo=self.alpha_homeo,
                                  method=self.fit_algorithm, nb_quant=self.nb_quant, C=self.C, do_sym=self.do_sym,
                                  batch_size=self.batch_size, record_each=self.record_each,
                                  do_mask=self.do_mask,
                                  verbose=self.verbose, random_state=self.random_state, do_HAP=self.do_HAP)

        if self.record_each==0:
            self.dictionary, self.precision, self.P_cum = return_fn
        else:
            self.dictionary, self.precision, self.P_cum, self.record = return_fn

    def transform(self, X, algorithm=None, l0_sparseness=None, fit_tol=None):
        """Fit the model from data in X.

        Parameters
        ----------
        X: array-like, shape (n_samples, n_pixels)
            Training vector, where n_samples in the number of samples
            and n_pixels is the number of features.

        Returns
        -------
        self : object
            Returns sparse code.
        """
        if algorithm is None:  algorithm = self.fit_algorithm
        if l0_sparseness is None:  l0_sparseness = self.l0_sparseness
        if fit_tol is None:  fit_tol = self.fit_tol
        return sparse_encode(X, self.dictionary, self.precision, algorithm=algorithm, P_cum=self.P_cum,
                                fit_tol=fit_tol, l0_sparseness=l0_sparseness)

def dict_learning(X, dictionary=None, precision=None, P_cum=None, eta=0.02, n_dictionary=2, l0_sparseness=10, fit_tol=None,
                  do_precision=False, n_iter=100, do_mask=True,
                       eta_homeo=0.01, alpha_homeo=0.02,
                       batch_size=100, record_each=0, record_num_batches = 1000, verbose=False,
                       method='mp', C=0., nb_quant=100, do_sym=True, random_state=None, do_HAP=False):
    """
    Solves a dictionary learning matrix factorization problem online.

    Finds the best dictionary and the corresponding sparse code for
    approximating the data matrix X by solving::


    Solves the optimization problem::

        (U^*, V^*) = argmin_{(U,V)} 0.5 || X - V^T * U ||_2^2
                                    + alpha * S( U )
                                    + alpha_homeo * H(V)

                     s. t. || U ||_0 = k

                    where S is a sparse representation cost,
                    and H a homeostatic representation cost.

    where V is the dictionary and U is the sparse code. This is
    accomplished by repeatedly iterating over mini-batches by slicing
    the input data.

    For instance,

        H(V) = \sum_{0 <= k < n_dictionary} (|| V_k ||_2^2 -1)^2

    Parameters
    ----------
    X: array of shape (n_samples, n_pixels)
        Data matrix.

    dictionary: array of shape (n_dictionary, n_pixels)
        Initialization for the dictionary. If None, we chose Gaussian noise.

    precision: array of shape (n_dictionary, n_pixels)
        Initialization for the precision matrix. If None, we chose a uniform matrix.

    n_dictionary : int,
        Number of dictionary atoms to extract.

    eta : float
        Gives the learning parameter for the homeostatic gain.

    n_iter : int,
        total number of iterations to perform

    eta_homeo : float
        Gives the learning parameter for the homeostatic gain.

    alpha_homeo : float
        Gives the smoothing exponent  for the homeostatic gain
        If equal to 1 the homeostatic learning rule learns a linear relation to
        variance.
        If equal to zero, we use COMP

    nb_quant : int,
        number of bins for the quantification used in the homeostasis

    C : float
        characteristic scale for the quantization.
        Use C=0. to have an adaptive scaling.

    dictionary : array of shape (n_dictionary, n_pixels),
        initial value of the dictionary for warm restart scenarios

    fit_algorithm : {'mp', 'omp', 'comp', 'lars', 'cd'}
        see sparse_encode

    batch_size : int,
        The number of samples to take in each batch.

    l0_sparseness : int, ``0.1 * n_pixels`` by default
        Number of nonzero coefficients to target in each column of the
        solution. This is only used by `algorithm='lars'`, `algorithm='mp'`  and
        `algorithm='omp'`.

    fit_tol : float, 1. by default
        If `algorithm='lasso_lars'` or `algorithm='lasso_cd'`, `fit_tol` is the
        penalty applied to the L1 norm.
        If `algorithm='threshold'`, `fit_tol` is the absolute value of the
        threshold below which coefficients will be squashed to zero.
        If `algorithm='mp'` or `algorithm='omp'`, `fit_tol` is the tolerance
        parameter: the value of the reconstruction error targeted. In this case,
        it overrides `l0_sparseness`.

    do_precision: boolean
        Switch to perform or not a precision-weighted learning.

    do_mask: boolean
        A switch to learn the filters just on a disk. This allows to control for potential
        problems with the fact that images atre sampled on a square grid.

    record_each :
        if set to 0, it does nothing. Else it records every record_each step the
        statistics during the learning phase (variance and kurtosis of coefficients).

    record_num_batches :
        number of batches used to make statistics (if -1, uses the whole training set)

    verbose :
        degree of verbosity of the printed output

    Returns
    -------

    dictionary : array of shape (n_dictionary, n_pixels),
        the solutions to the dictionary learning problem

    """

    if record_each>0:
        import pandas as pd
        record = pd.DataFrame()

    if n_dictionary is None:
        n_dictionary = X.shape[1]

    t0 = time.time()
    n_samples, n_pixels = X.shape

    if dictionary is None:
        dictionary = np.random.randn(n_dictionary, n_pixels)

    norm = np.sqrt(np.sum(dictionary**2, axis=1))
    dictionary /= norm[:, np.newaxis]
    norm = np.sqrt(np.sum(dictionary**2, axis=1))

    #if not precision is None: do_precision = True
    if do_precision:
        precision = np.ones((n_dictionary, n_pixels))

    if verbose == 1:
        print('[dict_learning]', end=' ')

    # print(alpha_homeo, eta_homeo, alpha_homeo==0, eta_homeo==0, alpha_homeo==0 or eta_homeo==0, 'P_cum', P_cum)

    if do_mask:
        N_X = N_Y = np.sqrt(n_pixels)
        x , y = np.meshgrid(np.linspace(-1, 1, N_X), np.linspace(-1, 1, N_Y))
        #R = np.sqrt(x ** 2 + y ** 2)
        #mask = (((np.cos(np.pi * R) + 1) / 2 * (R < 1.)) ** (1/8)).ravel()
        #mask[mask>0.1] = 1
        mask = (np.sqrt(x ** 2 + y ** 2) < 1).astype(np.float).ravel()

    # splits the whole dataset into batches
    n_batches = n_samples // batch_size
    X_train = X.copy()
    if do_mask:
        X_train = X_train * mask[np.newaxis, :]
    # Modifies the sequence in-place by shuffling its contents; Multi-dimensional arrays are only shuffled along the first axis:
    np.random.shuffle(X_train)
    # Splits into ``n_batches`` batches
    batches = np.array_split(X_train, n_batches)

    if alpha_homeo==0:
        gain = None
        # do the equalitarian homeostasis
        if P_cum is None:
            P_cum = np.linspace(0., 1., nb_quant, endpoint=True)[np.newaxis, :] * np.ones((n_dictionary, 1))
            if C == 0.:
                # initialize the rescaling vector
                from shl_scripts.shl_encode import get_rescaling
                corr = (batches[0] @ dictionary.T)
                C_vec = get_rescaling(corr, nb_quant=nb_quant, do_sym=do_sym, verbose=verbose)
                # and stack it to P_cum array for convenience
                P_cum = np.vstack((P_cum, C_vec))
    else:
        # do the classical homeostasis
        gain = np.ones(n_dictionary)
        mean_var = np.ones(n_dictionary)
        P_cum = None
        mean_measure = None

    import itertools
    # Return elements from list of batches until it is exhausted. Then repeat the sequence indefinitely.
    batches = itertools.cycle(batches)

    # cycle over all batches
    for ii, this_X in zip(range(n_iter), batches):
        dt = (time.time() - t0)
        if verbose > 0:
            if ii % int(n_iter//verbose + 1) == 0:
                print ("Iteration % 3i /  % 3i (elapsed time: % 3is, % 4.1fmn)"
                       % (ii, n_iter, dt, dt//60))

        # Sparse coding
        sparse_code = sparse_encode(this_X, dictionary, precision, algorithm=method, fit_tol=fit_tol,
                                   P_cum=P_cum, C=C, do_sym=do_sym, l0_sparseness=l0_sparseness,
                                   gain=gain)

        # Update dictionary
        residual = this_X - sparse_code @ dictionary
        residual /= n_batches # divide by the number of batches to get the average
        #dictionary *= np.sqrt(1-eta**2) # http://www.inference.vc/high-dimensional-gaussian-distributions-are-soap-bubble/
        dictionary += eta * (sparse_code.T @ residual)

        if do_precision:
            precision *= 1-eta
            precision += eta * ((sparse_code**2).T @ (1./(residual**2+1.e-6)))

        #if do_mask:
        #    dictionary = dictionary * mask[np.newaxis, :]

        # homeostasis
        norm = np.sqrt(np.sum(dictionary**2, axis=1)).T
        dictionary /= norm[:, np.newaxis]

        if eta_homeo>0.:
            if P_cum is None:
                # Update gain
                if mean_measure is None:
                    mean_measure = update_measure(np.ones(n_dictionary), sparse_code, eta_homeo=1, verbose=verbose, do_HAP=do_HAP)
                else:
                    mean_measure = update_measure(mean_measure, sparse_code, eta_homeo, verbose=verbose, do_HAP=do_HAP)
                gain = mean_measure**alpha_homeo
                #gain /= gain.mean()
                #dictionary /= gain[:, np.newaxis]
            else:
                if C==0.:
                    corr = (this_X @ dictionary.T)
                    C_vec = get_rescaling(corr, nb_quant=nb_quant, do_sym=do_sym, verbose=verbose)
                    P_cum[:-1, :] = update_P_cum(P_cum=P_cum[:-1, :],
                                                 code=sparse_code, eta_homeo=eta_homeo,
                                                 C=P_cum[-1, :], nb_quant=nb_quant, do_sym=do_sym,
                                                 verbose=verbose)
                    P_cum[-1, :] = (1 - eta_homeo) * P_cum[-1, :] + eta_homeo * C_vec
                else:
                    P_cum = update_P_cum(P_cum, sparse_code, eta_homeo,
                                         nb_quant=nb_quant, verbose=verbose, C=C, do_sym=do_sym)

        if record_each>0:
            if ii % int(record_each) == 0:
                from scipy.stats import kurtosis
                indx = np.random.permutation(X_train.shape[0])[:record_num_batches]
                sparse_code_rec = sparse_encode(X_train[indx, :], dictionary, precision, algorithm=method, fit_tol=fit_tol,
                                          P_cum=P_cum, do_sym=do_sym, C=C, l0_sparseness=l0_sparseness)
                # calculation of relative entropy
                p_ = np.count_nonzero(sparse_code_rec,axis=0) / (sparse_code_rec.shape[1])
                p_ /= p_.sum()
                rel_ent = np.sum(-p_ * np.log(p_)) / np.log(sparse_code_rec.shape[1])
                error = np.linalg.norm(X_train[indx, :] - sparse_code_rec @ dictionary)/record_num_batches

                record_one = pd.DataFrame([{'kurt':kurtosis(sparse_code_rec, axis=0),
                                            'prob_active':np.mean(np.abs(sparse_code_rec)>0, axis=0),
                                            'var':np.mean(sparse_code_rec**2, axis=0),
                                            'error':error,
                                            'entropy':rel_ent}],
                                            index=[ii])
                record = pd.concat([record, record_one])

    if verbose > 1:
        print('Learning code...', end=' ')
    elif verbose == 1:
        print('|', end=' ')

    if verbose > 1:
        dt = (time.time() - t0)
        print('done (total time: % 3is, % 4.1fmn)' % (dt, dt / 60))

    if record_each==0:
        return dictionary, precision, P_cum
    else:
        return dictionary, precision, P_cum, record

def update_measure(mean_measure, code, eta_homeo, verbose=False, do_HAP=False):
    """Update the estimated variance of coefficients in place.

    Following the classical SparseNet algorithm from Olshausen, we
    compute here a "gain vector" for the dictionary. This gain will
    be used to tune the weight of each dictionary element.

    The heuristics used here follows the assumption that during learning,
    some elements that learn first are more responsive to input patches
    as may be recorded by estimating their mean variance. If we were to
    keep their norm fixed, these would be more likely to be selected again,
    leading to a ``monopolistic'' distribution of dictionary elements,
    some having learned more often than others. By dividing their norm
    by their mean estimated variance, we lower the probability of elements
    with high variance to be selected again. This thus helps the learning
    to be more balanced.

    Parameters
    ----------
    mean_measure: array of shape (n_dictionary)
        Value of the dictionary' norm at the previous iteration.

    code: array of shape (n_dictionary, n_samples)
        Sparse coding of the data against which to optimize the dictionary.

    eta_homeo: float
        Gives the learning parameter for the gain.

    verbose:
        Degree of output the procedure will print.

    Returns
    -------
    gain: array of shape (n_dictionary)
        Updated value of the dictionary' norm.

    """
    if code.ndim == 1:
        code = code[:, np.newaxis]
    if eta_homeo>0.:
        if do_HAP:
            mean_measure_ = np.mean(code**2, axis=0)/np.mean(code**2)
        else:
            counts = np.count_nonzero(code, axis=0)
            mean_measure_ = counts / counts.sum()
        mean_measure = (1 - eta_homeo)*mean_measure + eta_homeo * mean_measure_

    return mean_measure


def update_P_cum(P_cum, code, eta_homeo, C, nb_quant=100, do_sym=True, verbose=False):
    """Update the estimated modulation function in place.

    Parameters
    ----------
    P_cum: array of shape (n_samples, n_components)
        Value of the modulation function at the previous iteration.

    dictionary: array of shape (n_components, n_features)
        The dictionary matrix against which to solve the sparse coding of
        the data. Some of the algorithms assume normalized rows for meaningful
        output.

    code: array of shape (n_samples, n_features)
        Data matrix.

    eta_homeo: float
        Gives the learning parameter for the mod.

    verbose:
        Degree of output the procedure will print.

    Returns
    -------
    P_cum: array of shape (n_samples, n_components)
        Updated value of the modulation function.

    """

    if eta_homeo>0.:
        P_cum_ = get_P_cum(code, nb_quant=nb_quant, C=C, do_sym=do_sym, verbose=verbose)
        P_cum = (1 - eta_homeo)*P_cum + eta_homeo * P_cum_
    return P_cum

def get_P_cum(code, C, nb_quant=100, do_sym=True, verbose=False):
    from shl_scripts.shl_encode import rescaling
    p_c = rescaling(code, C, do_sym=do_sym, verbose=verbose)

    n_samples, nb_filter = code.shape
    code_bins = np.linspace(0., 1., nb_quant, endpoint=True)
    P_cum = np.zeros((nb_filter, nb_quant))

    for i in range(nb_filter):
        p, bins = np.histogram(p_c[:, i], bins=code_bins, density=True)
        p /= p.sum()
        P_cum[i, :] = np.hstack((0, np.cumsum(p)))
    return P_cum
