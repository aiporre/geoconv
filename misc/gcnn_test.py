from tensorflow.keras.layers import Input, Dense
from tensorflow.keras import Model
from datetime import datetime

from gcnn import ConvGeodesic
from dataset.MPI_FAUST.tf_dataset import load_preprocessed_faust

import tensorflow as tf
import sys


def train_step(nn, data, step):
    (shot, bc), y = data

    with tf.GradientTape() as tape:
        y_pred = nn((shot, bc), training=True)
        loss = nn.compiled_loss(y, y_pred, regularization_losses=nn.losses)

    trainable_vars = nn.trainable_variables
    gradients = tape.gradient(loss, trainable_vars)

    zipped = list(zip(gradients, trainable_vars))
    nn.optimizer.apply_gradients(zipped)

    nn.compiled_metrics.update_state(y, y_pred)

    for grad, var in zipped:
        tf.summary.histogram(f"gradient_{var.name}", grad, step=step)

    for var in nn.trainable_variables:
        tf.summary.histogram(var.name, var, step=step)

    tf.summary.scalar("Manual loss tracking", loss, step=step)
    for metric in nn.metrics:
        tf.summary.scalar(metric.name, metric.result(), step=step)


if __name__ == "__main__":

    # Define model
    signal_input = Input(shape=(6890, 1056))
    bary_input = Input(shape=(6890, 4, 2, 6))
    down_scaling = Dense(16, activation="relu")(signal_input)
    geodesic_conv = ConvGeodesic(
        kernel_size=(2, 4), output_dim=16, amt_kernel=2, activation="relu"
    )([down_scaling, bary_input])
    up_scaling = Dense(6890, activation="relu")(geodesic_conv)
    model = Model(inputs=[signal_input, bary_input], outputs=[up_scaling])
    model.compile(
        optimizer="adam",
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["sparse_categorical_accuracy"]
    )
    model.summary()

    # Get data
    tf_faust_dataset = load_preprocessed_faust(
        "/home/andreas/PycharmProjects/Masterarbeit/dataset/MPI_FAUST/preprocessed_registrations.zip"
    )

    # Logs
    logdir = "./logs/fit/" + datetime.now().strftime("%Y%m%d-%H%M%S")
    writer = tf.summary.create_file_writer(logdir)
    epochs = 10
    with writer.as_default():
        training_step = 0
        for _ in range(epochs):
            for elem in tf_faust_dataset.take(80).batch(4):
                sys.stdout.write(f"\rTrain step: {training_step}")
                train_step(model, elem, training_step)
                training_step += 1
