
from __future__ import absolute_import
from keras_unet.layer_utils import *

from tensorflow.keras.layers import Input, Conv2D
from tensorflow.keras.layers import BatchNormalization, Activation, concatenate, multiply
from tensorflow.keras.layers import ReLU, LeakyReLU, PReLU, ELU
from tensorflow.keras.models import Model

def unet_2d(input_size, feature_list, n_labels, 
            activation='ReLU', output_activation='Softmax', 
            batch_norm=False, pool=True, unpool=True, name='unet'):
    '''
    U-net 
    ----------
    Ronneberger, O., Fischer, P. and Brox, T., 2015, October. U-net: Convolutional networks for biomedical image segmentation. 
    In International Conference on Medical image computing and computer-assisted intervention (pp. 234-241). Springer, Cham.
    
    Input
    ----------
        input_size: a tuple that defines the shape of input, e.g., (None, None, 3)
        feature_list: an iterable that defines the int number of filters for each \
                      down- and upsampling level. E.g., [64, 128, 256, 512]
                      the depth is expected as `len(feature_list)`
        n_labels: int number of output labels, must larger than 1
        activation: one of the `tensorflow.keras.layers` interface, e.g., ReLU
        output_activation: one of the `tensorflow.keras.layers` interface. Default option is Softmax
                           if None is received, then linear activation is applied, that said, not activation.
        batch_norm: True for batch normalization, False otherwise.
        pool: True for maxpooling, False for strided convolutional layers.
        unpool: True for unpooling (i.e., reflective padding), False for transpose convolutional layers.                 
        name: name of the created keras layers
    Output
    ----------
        X: a keras model 
    
    '''
    activation_func = eval(activation)

    IN = Input(input_size)
    X = IN
    X_skip = []
    
    # downsampling blocks
    X = CONV_stack(X, feature_list[0], stack_num=2, activation=activation, batch_norm=batch_norm, name='{}_down0'.format(name))
    X_skip.append(X)
    
    for i, f in enumerate(feature_list[1:]):
        X = UNET_left(X, f, activation=activation, pool=pool, batch_norm=batch_norm, name='{}_down{}'.format(name, i+1))        
        X_skip.append(X)
    
    # upsampling blocks
    X_skip = X_skip[:-1][::-1]
    for i, f in enumerate(feature_list[:-1][::-1]):
        X = UNET_right(X, X_skip[i], f, activation=activation, 
                       unpool=unpool, batch_norm=batch_norm, name='{}_up{}'.format(name, i+1))

    OUT = CONV_output(X, n_labels, kernel_size=1, activation=output_activation, name='{}_output'.format(name))
    model = Model(inputs=[IN], outputs=[OUT])
    
    return model    

def unet_plus_2d(input_size, feature_list, n_labels, 
         activation='ReLU', output_activation='Softmax', 
         batch_norm=False, pool=True, unpool=True, name='xnet'):
    '''
    U-net++ or nested U-net 
    ----------
    Zhou, Z., Siddiquee, M.M.R., Tajbakhsh, N. and Liang, J., 2018. Unet++: A nested u-net architecture for medical image segmentation. 
    In Deep Learning in Medical Image Analysis and Multimodal Learning for Clinical Decision Support (pp. 3-11). Springer, Cham.
    
    Input
    ----------
        input_size: a tuple that defines the shape of input, e.g., (None, None, 3)
        feature_list: an iterable that defines the int number of filters for each \
                      down- and upsampling level. E.g., [64, 128, 256, 512]
                      the depth is expected as `len(feature_list)`
        n_labels: int number of output labels, must larger than 1
        activation: one of the `tensorflow.keras.layers` interface, e.g., ReLU
        output_activation: one of the `tensorflow.keras.layers` interface. Default option is Softmax
                           if None is received, then linear activation is applied, that said, not activation.
        batch_norm: True for batch normalization, False otherwise.
        pool: True for maxpooling, False for strided convolutional layers.
        unpool: True for unpooling (i.e., reflective padding), False for transpose convolutional layers.                 
        name: name of the created keras layers
    Output
    ----------
        X: a keras model 
    
    '''
    
    depth_ = len(feature_list)
    
    IN = Input(input_size)
    X = IN
    
    # allocate nested lists for collecting output tensors 
    X_nest_skip = [[] for _ in range(depth_)] 
    
    # downsampling blocks (same as in 'unet_2d')
    X = CONV_stack(X, feature_list[0], stack_num=2, activation=activation, batch_norm=batch_norm, name='{}_down0'.format(name))
    X_nest_skip[0].append(X)
    for i, f in enumerate(feature_list[1:]):
        X = UNET_left(X, f, activation=activation, pool=pool, batch_norm=batch_norm, name='{}_down{}'.format(name, i+1))        
        X_nest_skip[0].append(X)
    
    for nest_lev in range(1, depth_):
        
        # subset filter numbers to the current upsampling level
        feature_list_sub = feature_list[:(depth_-nest_lev)]
        
        # loop over individual upsamling levels
        for i, f in enumerate(feature_list_sub[::-1]):
            
            # collecting previous downsampling outputs
            previous_skip = []
            for previous_lev in range(nest_lev):
                previous_skip.append(X_nest_skip[previous_lev][i])
                
            # upsamping block that concatenates all available (same feature map size) down-/upsampling outputs
            X_nest_skip[nest_lev].append(
                XNET_right(X_nest_skip[nest_lev-1][i+1], previous_skip, feature_list[i], activation=activation, name='xnet_{}{}'.format(nest_lev, i)))
            
    # output
    OUT = CONV_output(X_nest_skip[-1][-1], n_labels, kernel_size=1, activation=output_activation, name='{}_output'.format(name))
    
    # model
    model = Model(inputs=[IN], outputs=[OUT])
    
    return model

def att_unet_2d(input_size, feature_list, n_labels, 
             activation='ReLU', atten_activation='ReLU', attention='add', output_activation='Softmax', 
             batch_norm=False, pool=True, unpool=True, name='att-unet'):
    '''
    Attention-U-net 
    ----------
    Oktay, O., Schlemper, J., Folgoc, L.L., Lee, M., Heinrich, M., Misawa, K., Mori, K., McDonagh, S., Hammerla, N.Y., Kainz, B. 
    and Glocker, B., 2018. Attention u-net: Learning where to look for the pancreas. arXiv preprint arXiv:1804.03999.
    
    Input
    ----------
        input_size: a tuple that defines the shape of input, e.g., (None, None, 3)
        feature_list: an iterable that defines the int number of filters for each \
                      down- and upsampling level. E.g., [64, 128, 256, 512]
                      the depth is expected as `len(feature_list)`
        n_labels: int number of output labels, must larger than 1
        activation: one of the `tensorflow.keras.layers` interface, e.g., ReLU
        atten_activation: a nonlinear attnetion activation.
                    The `sigma_1` in Oktay et al. 2018. Default is ReLU
        attention: 'add' for additive attention. 'multiply' for multiplicative attention.
                   Oktay et al. 2018 applied additive attention.
        output_activation: one of the `tensorflow.keras.layers` interface. Default option is Softmax
                           if None is received, then linear activation is applied, that said, not activation.
        batch_norm: True for batch normalization, False otherwise.
        pool: True for maxpooling, False for strided convolutional layers.
        unpool: True for unpooling (i.e., reflective padding), False for transpose convolutional layers.                 
        name: name of the created keras layers
    Output
    ----------
        X: a keras model 
    
    '''
    
    # one of the ReLU, LeakyReLU, PReLU, ELU
    activation_func = eval(activation)

    IN = Input(input_size)
    X = IN
    X_skip = []
    
    # downsampling blocks
    X = CONV_stack(X, feature_list[0], stack_num=2, activation=activation, batch_norm=batch_norm, name='{}_down0'.format(name))
    X_skip.append(X)
    
    for i, f in enumerate(feature_list[1:]):
        X = UNET_left(X, f, activation=activation, pool=pool, batch_norm=batch_norm, name='{}_down{}'.format(name, i+1))        
        X_skip.append(X)
        
    # upsampling blocks
    X_skip = X_skip[:-1][::-1]
    for i, f in enumerate(feature_list[:-1][::-1]):
        X = UNET_att_right(X, X_skip[i], f, att_channel=f//2, 
                           activation=activation, atten_activation=atten_activation, attention=attention,
                           unpool=unpool, batch_norm=batch_norm, name='{}_up{}'.format(name, i+1))

    OUT = CONV_output(X, n_labels, kernel_size=1, activation=output_activation, name='{}_output'.format(name))
    model = Model(inputs=[IN], outputs=[OUT])
    
    return model




