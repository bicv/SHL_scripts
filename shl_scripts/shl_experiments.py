#!/usr/bin/env python
# -*- coding: utf-8 -*
from __future__ import division, print_function, absolute_import
from shl_scripts.shl_tools import get_data
from shl_scripts.shl_encode import sparse_encode
from shl_scripts import shl_tools

"""

========================================================
Learning filters from natural images using sparse coding
========================================================

* When imposing a code representing patches from natural images to be sparse,
one observes the formation of filters ressembling the receptive field of simple
cells in primates primary visual cortex.  This was first proposed in the
framework of the SparseNet algorithm from Bruno Olshausen
(http://redwood.berkeley.edu/bruno/sparsenet/).

* This particular implementation has been published as Perrinet, Neural
Computation (2010) (see http://invibe.net/LaurentPerrinet/Publications/Perrinet10shl )::

   @article{Perrinet10shl,
        Author = {Perrinet, Laurent U.},
        Title = {Role of homeostasis in learning sparse representations},
        Year = {2010}
        Url = {http://invibe.net/LaurentPerrinet/Publications/Perrinet10shl},
        Doi = {10.1162/neco.2010.05-08-795},
        Journal = {Neural Computation},
        Volume = {22},
        Number = {7},
        Keywords = {Neural population coding, Unsupervised learning, Statistics of natural images, Simple cell receptive fields, Sparse Hebbian Learning, Adaptive Matching Pursuit, Cooperative Homeostasis, Competition-Optimized Matching Pursuit},
        Month = {July},
        }


"""

import time
import os

toolbar_width = 40

# import matplotlib

import numpy as np
# see https://github.com/bicv/SLIP/blob/master/SLIP.ipynb
from SLIP import Image

import warnings
warnings.simplefilter('ignore', category=RuntimeWarning)

def touch(fname):
    open(fname, 'w').close()

class SHL(object):
    """

    Base class to define SHL experiments:
        - initialization
        - coding and learning
        - visualization
        - quantitative analysis

    """
    def __init__(self,
                 height=256,
                 width=256,
                 patch_size=(12, 12),
                 database = 'database/',
                 n_dictionary=14**2,
                 learning_algorithm='mp',
                 fit_tol=None,
                 l0_sparseness=10,
                 n_iter=2**14,
                 eta=.01,
                 eta_homeo=.05,
                 alpha_homeo=.2,
                 max_patches=1024,
                 batch_size=256,
                 record_each=200,
                 n_image=200,
                 DEBUG_DOWNSCALE=1, # set to 10 to perform a rapid experiment
                 verbose=0,
                 data_cache = './data_cache',
                 ):
        self.height = height
        self.width = width
        self.database = database
        self.patch_size = patch_size
        self.n_dictionary = n_dictionary
        self.n_iter = int(n_iter/DEBUG_DOWNSCALE)
        self.max_patches = int(max_patches/DEBUG_DOWNSCALE)
        self.n_image = int(n_image/DEBUG_DOWNSCALE)
        self.batch_size = batch_size
        self.learning_algorithm = learning_algorithm
        self.fit_tol = fit_tol

        self.l0_sparseness = l0_sparseness
        self.eta = eta
        self.eta_homeo = eta_homeo
        self.alpha_homeo = alpha_homeo

        self.record_each = int(record_each/DEBUG_DOWNSCALE)
        self.verbose = verbose
        # assigning and create a folder for caching data
        self.data_cache = './data_cache'
        if not self.data_cache is None:
            try:
                os.mkdir(self.data_cache)
            except:
                pass

        # creating a tag related to this process
        PID, HOST = os.getpid(), os.uname()[1]
        self.LOCK = '_lock' + '_pid-' + str(PID) + '_host-' + HOST


        # Load natural images and extract patches
        self.slip = Image({'N_X':height, 'N_Y':width,
                                        'white_n_learning' : 0,
                                        'seed': None,
                                        'white_N' : .07,
                                        'white_N_0' : .0, # olshausen = 0.
                                        'white_f_0' : .4, # olshausen = 0.2
                                        'white_alpha' : 1.4,
                                        'white_steepness' : 4.,
                                        'datapath': self.database,
                                        'do_mask':True,
                                        'N_image': n_image})

    def get_data(self, name_database='serre07_distractors', seed=None, patch_norm=True):
        self.coding=np.ones(((self.max_patches * self.n_image),self.n_dictionary))
        return get_data(height=self.height, width=self.width, n_image=self.n_image,
                    patch_size=self.patch_size, datapath=self.database, name_database=name_database,
                    max_patches=self.max_patches, seed=None, patch_norm=True,
                    verbose=self.verbose)


    def code(self, data, dico, coding_algorithm='mp', **kwargs):
        if self.verbose:
            print('Coding data with algorithm ', coding_algorithm,  end=' ')
            t0 = time.time()

        #sparse_code = dico.transform(data, algorithm=coding_algorithm)
        #patches = np.dot(sparse_code, dico.dictionary)
        self.coding = sparse_encode(data, dico.dictionary,
                                                algorithm=self.learning_algorithm, l0_sparseness=self.l0_sparseness,
                                               fit_tol=None, mod=None, verbose=0)

        if self.verbose:
            dt = time.time() - t0
            print('done in %.2fs.' % dt)
        #return patches

    def learn_dico(self, data=None, name_database='serre07_distractors',
                   matname=None, list_figures=[], **kwargs):
        if matname is None:
            if data is None: data = self.get_data(name_database)
            # Learn the dictionary from reference patches
            if self.verbose: print('Learning the dictionary with algo = self.learning_algorithm', end=' ')
            t0 = time.time()
            from shl_scripts.shl_learn import SparseHebbianLearning
            dico = SparseHebbianLearning(fit_algorithm=self.learning_algorithm,
                                         n_dictionary=self.n_dictionary, eta=self.eta, n_iter=self.n_iter,
                                         eta_homeo=self.eta_homeo, alpha_homeo=self.alpha_homeo,
                                         dict_init=None, l0_sparseness=self.l0_sparseness,
                                         batch_size=self.batch_size, verbose=self.verbose,
                                         fit_tol=self.fit_tol,
                                         record_each=self.record_each)
            if self.verbose: print('Training on %d patches' % len(data), end='... ')
            dico.fit(data)

            if self.verbose:
                dt = time.time() - t0
                print('done in %.2fs.' % dt)

        else:
            import pickle
            fmatname = os.path.join(self.data_cache, matname)
            if not(os.path.isfile(fmatname)):
                time.sleep(np.random.rand()*0.1)
                if not(os.path.isfile(fmatname + '_lock')):
                    touch(fmatname + '_lock')
                    touch(fmatname + self.LOCK)
                    dico = self.learn_dico(data=data, name_database=name_database,
                                           record_each=self.record_each, matname=None, **kwargs)
                    with open(fmatname, 'wb') as fp:
                        pickle.dump(dico, fp)
                    try:
                        os.remove(fmatname + self.LOCK)
                        os.remove(fmatname + '_lock')
                    except:
                        print('Coud not remove ', fmatname + LOCK)
                else:
                    dico = 'lock'
                    print('the computation is locked', fmatname + LOCK)
            else:
                with open(fmatname, 'rb') as fp:
                    dico = pickle.load(fp)


        # self.coding = shl_encode.sparse_encode(data, dico.dictionary,
        #                                         algorithm=self.learning_algorithm, l0_sparseness=self.l0_sparseness,
        #                                        fit_tol=None, mod=None, verbose=0)
        #
        self.code(data, dico)

        if not dico == 'lock':
            if 'show_dico' in list_figures:
                fig, ax = self.show_dico(title=matname)
                fig.show()
            if 'show_dico_in_order' in list_figures:
                fig,ax=self.show_dico_in_order(title=matname)
                fig.show()
            if 'plot_variance' in list_figures:
                fig, ax = self.plot_variance(data=data)
                fig.show()
            if 'plot_variance_histogram' in list_figures:
                fig, ax = self.plot_variance_histogram(data=data)
                fig.show()
            if 'time_plot_var' in list_figures:
                fig, ax = self.time_plot(variable='var');
                fig.show()
            if 'time_plot_kurt' in list_figures:
                fig, ax = self.time_plot(variable='kurt');
                fig.show()
            if 'time_plot_prob' in list_figures:
                fig, ax = self.time_plot(variable='prob_active');
                fig.show()

        self.dico_exp = dico

        return self.dico_exp

    def plot_variance(self, data=None, algorithm=None, fname=None):
        return shl_tools.plot_variance(self, data=data, fname=fname, algorithm=algorithm)

    def plot_variance_histogram(self, data=None, algorithm=None, fname=None):
        return shl_tools.plot_variance_histogram(self, data=data, fname=fname, algorithm=algorithm)

    def time_plot(self, variable='kurt', fname=None, N_nosample=1):
        return shl_tools.time_plot(self, variable=variable, fname=fname, N_nosample=N_nosample)

    def show_dico(self, title=None, fname=None):
        return shl_tools.show_dico(self, title=title, fname=fname)

    def show_dico_in_order(self,data=None,title=None,fname=None):
        return shl_tools.show_dico_in_order(self,title=title,fname=fname)

if __name__ == '__main__':
    DEBUG_DOWNSCALE, verbose = 10, 100 #faster, with verbose output
    DEBUG_DOWNSCALE, verbose = 1, 0
    shl = SHL(DEBUG_DOWNSCALE=DEBUG_DOWNSCALE, learning_algorithm='mp', verbose=verbose)
    dico = shl.learn_dico()
    import matplotlib.pyplot as plt

    fig, ax = dico.show_dico()
    plt.savefig('assc.png')
    plt.show()