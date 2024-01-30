from geoconv.layers.angular_max_pooling import AngularMaxPooling
from geoconv.layers.conv_geodesic import ConvGeodesic
from geoconv.layers.conv_zero import ConvZero
from geoconv.layers.conv_dirac import ConvDirac
from tensorflow import keras

import tensorflow as tf


class Imcnn(tf.keras.Model):
    def __init__(self, signal_dim, kernel_size, template_radius, splits, layer_conf=None, variant="dirac"):
        super().__init__()
        self.signal_dim = signal_dim
        self.kernel_size = kernel_size
        self.template_radius = template_radius
        self.splits = splits

        if variant == "dirac":
            self.layer_type = ConvDirac
        elif variant == "geodesic":
            self.layer_type = ConvGeodesic
        elif variant == "zero":
            self.layer_type = ConvZero
        else:
            raise RuntimeError("Select a layer type from: ['dirac', 'geodesic', 'zero']")

        if layer_conf is None:
            self.output_dims = [96, 256, 384, 384]
            self.rotation_deltas = [1 for _ in range(len(self.output_dims))]
        else:
            self.output_dims, self.rotation_deltas = list(zip(*layer_conf))

        #################
        # Handling Input
        #################
        self.normalize = keras.layers.Normalization(axis=-1, name="input_normalization")
        self.downsize_dense = keras.layers.Dense(64, activation="relu", name="downsize")
        self.downsize_bn = keras.layers.BatchNormalization(axis=-1, name="BN_downsize")

        ##################
        # Global Features
        ##################
        self.isc_layers = []
        self.bn_layers = []
        self.do_layers = []
        self.amp_layers = []
        for idx in range(len(self.output_dims)):
            self.isc_layers.append(
                self.layer_type(
                    amt_templates=self.output_dims[idx],
                    template_radius=self.template_radius,
                    activation="relu",
                    name=f"ISC_layer_{idx}",
                    splits=self.splits,
                    rotation_delta=self.rotation_deltas[idx]
                )
            )
            self.bn_layers.append(keras.layers.BatchNormalization(axis=-1, name=f"BN_layer_{idx}"))
            self.do_layers.append(keras.layers.Dropout(rate=0.2, name=f"DO_layer_{idx}"))
            self.amp_layers.append(AngularMaxPooling())

        #########
        # Output
        #########
        self.output_dense = keras.layers.Dense(6890, name="output")

    def call(self, inputs, orientations=None, training=None, mask=None):
        #################
        # Handling Input
        #################
        signal, bc = inputs
        signal = self.normalize(signal)
        signal = self.downsize_dense(signal)
        signal = self.downsize_bn(signal)

        ###############
        # Forward pass
        ###############
        for idx in range(len(self.output_dims)):
            signal = self.do_layers[idx](signal)
            signal = self.isc_layers[idx]([signal, bc])
            signal = self.amp_layers[idx](signal)
            signal = self.bn_layers[idx](signal)

        #########
        # Output
        #########
        return self.output_dense(signal)
