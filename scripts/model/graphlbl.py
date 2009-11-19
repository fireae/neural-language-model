"""
Theano graph of Mnih log bi-linear model.
"""

import theano

from theano import tensor as t
from theano import scalar as s

from theano.tensor.basic import horizontal_stack
from theano.tensor import dot

from theano import gradient

import theano.compile
#from miscglobals import LINKER, OPTIMIZER
#mode = theano.compile.Mode(LINKER, OPTIMIZER)
COMPILE_MODE = theano.compile.Mode('c|py', 'fast_run')
#COMPILE_MODE = theano.compile.Mode('py', 'fast_compile')

import numpy

from common.chopargs import chopargs

output_weights = t.dmatrix()
output_biases = t.dmatrix()

# TODO: Include gradient steps in actual function, don't do them manually

def activation_function(r):
    from hyperparameters import HYPERPARAMETERS
    if HYPERPARAMETERS["ACTIVATION_FUNCTION"] == "sigmoid":
        return sigmoid(r)
    elif HYPERPARAMETERS["ACTIVATION_FUNCTION"] == "tanh":
        return t.tanh(r)
    elif HYPERPARAMETERS["ACTIVATION_FUNCTION"] == "softsign":
        from theano.sandbox.softsign import softsign
        return softsign(r)
    else:
        assert 0

def stack(x):
    """
    Horizontally stack a list of representations, and then compress them to
    one representation.
    """
    assert len(x) >= 2
    return horizontal_stack(*x)

def score(targetrepr, predictrepr):
    # TODO: Is this the right scoring function?
    score = dot(targetrepr, predictrepr.T)
    return score

cached_functions = {}
def functions(sequence_length):
    """
    Return two functions
     * The first function does prediction.
     * The second function does learning.
    """
    p = (sequence_length)
    if p not in cached_functions:
        print "Need to construct graph for sequence_length=%d..." % (sequence_length)
        # Create the sequence_length inputs.
        # Each is a t.dmatrix(), initial word embeddings (provided by
        # Jason + Ronan) to be transformed into an initial representation.
        # We could use a vector, but instead we use a matrix with one row.
        sequence = [t.dmatrix() for i in range(sequence_length)]
        correct_repr = t.dmatrix()
        noise_repr = t.dmatrix()

        stackedsequence = stack(sequence)
        predictrepr = dot(stackedsequence, output_weights) + output_biases

        correct_score = score(correct_repr, predictrepr)
        noise_score = score(noise_repr, predictrepr)
        loss = t.clip(1 - correct_score + noise_score, 0, 1e999)

        (doutput_weights, doutput_biases) = t.grad(loss, [output_weights, output_biases])
        dsequence = t.grad(loss, sequence)
        (dcorrect_repr, dnoise_repr) = t.grad(loss, [correct_repr, noise_repr])
        #print "REMOVEME", len(dcorrect_inputs)
        predict_inputs = sequence + [correct_repr, output_weights, output_biases]
        train_inputs = sequence + [correct_repr, noise_repr, output_weights, output_biases]
#        verbose_predict_inputs = predict_inputs
        predict_outputs = [predictrepr, correct_score]
        train_outputs = [loss, predictrepr, correct_score, noise_score] + dsequence + [dcorrect_repr, dnoise_repr, doutput_weights, doutput_biases]
#        train_outputs = [loss, correct_repr, correct_score, noise_repr, noise_score]
#        verbose_predict_outputs = [correct_score, correct_prehidden]

        import theano.gof.graph

        nnodes = len(theano.gof.graph.ops(predict_inputs, predict_outputs))
        print "About to compile predict function over %d ops [nodes]..." % nnodes
        predict_function = theano.function(predict_inputs, predict_outputs, mode=COMPILE_MODE)
        print "...done constructing graph for sequence_length=%d" % (sequence_length)

#        nnodes = len(theano.gof.graph.ops(verbose_predict_inputs, verbose_predict_outputs))
#        print "About to compile predict function over %d ops [nodes]..." % nnodes
#        verbose_predict_function = theano.function(verbose_predict_inputs, verbose_predict_outputs, mode=COMPILE_MODE)
#        print "...done constructing graph for sequence_length=%d" % (sequence_length)

        nnodes = len(theano.gof.graph.ops(train_inputs, train_outputs))
        print "About to compile train function over %d ops [nodes]..." % nnodes
        train_function = theano.function(train_inputs, train_outputs, mode=COMPILE_MODE)
        print "...done constructing graph for sequence_length=%d" % (sequence_length)

#        cached_functions[p] = (predict_function, train_function, verbose_predict_function)
        cached_functions[p] = (predict_function, train_function)
    return cached_functions[p]

#def apply_function(fn, sequence, target_output, parameters):
#    assert len(sequence) == parameters.hidden_width
#    inputs = [numpy.asarray([token]) for token in sequence]
#    if target_output != None:
##        if HYPERPARAMETERS["USE_SECOND_HIDDEN_LAYER"]:
##            return fn(*(inputs + [numpy.asarray([target_output]), parameters.hidden_weights, parameters.hidden_biases, parameters.hidden2_weights, parameters.hidden2_biases, parameters.output_weights, parameters.output_biases]))
##        else:
#        return fn(*(inputs + [numpy.asarray([target_output]), parameters.hidden_weights, parameters.hidden_biases, parameters.output_weights, parameters.output_biases]))
#    else:
##        if HYPERPARAMETERS["USE_SECOND_HIDDEN_LAYER"]:
##            return fn(*(inputs + [parameters.hidden_weights, parameters.hidden_biases, parameters.hidden2_weights, parameters.hidden2_biases, parameters.output_weights, parameters.output_biases]))
##        else:
#        return fn(*(inputs + [parameters.hidden_weights, parameters.hidden_biases, parameters.output_weights, parameters.output_biases]))
#

#def predict(correct_sequence, parameters):
#    fn = functions(sequence_length=len(correct_sequence))[0]
#    r = fn(*(correct_sequence + [parameters.hidden_weights, parameters.hidden_biases, parameters.output_weights, parameters.output_biases]))
#    assert len(r) == 1
#    r = r[0]
#    assert r.shape == (1, 1)
#    return r[0,0]
#def verbose_predict(correct_sequence, parameters):
#    fn = functions(sequence_length=len(correct_sequence))[2]
#    r = fn(*(correct_sequence + [parameters.hidden_weights, parameters.hidden_biases, parameters.output_weights, parameters.output_biases]))
#    assert len(r) == 2
#    (score, prehidden) = r
#    assert score.shape == (1, 1)
#    return score[0,0], prehidden

def train(sequence, correct_repr, noise_repr, parameters):
    fn = functions(sequence_length=len(sequence))[1]
    r = fn(*(sequence + [correct_repr, noise_repr, parameters.output_weights, parameters.output_biases]))

    (loss, predictrepr, correct_score, noise_score, dsequence, dcorrect_repr, dnoise_repr, doutput_weights, doutput_biases) = chopargs(r, (0,0,0,0,len(sequence),0,0,0,0))
    dsequence = list(dsequence)
    return (loss, predictrepr, correct_score, noise_score, dsequence, dcorrect_repr, dnoise_repr, doutput_weights, doutput_biases)
