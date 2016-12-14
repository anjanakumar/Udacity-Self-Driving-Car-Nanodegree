import os
import cv2
import math
import numpy as np
import pandas as pd
import csv
import time
import argparse
import json
from keras.models import Sequential
from keras.layers.convolutional import Convolution2D
from keras.layers.pooling import MaxPooling2D
from keras.layers import Dense, Dropout, Flatten, Lambda, Activation
from keras.optimizers import Adam

import preprocess_input

# Number of images to process per row of CSV = 2 x center + left + right
# The 2x factor corresponds to the flipping operation
N_IMG_PER_ROW = 4

# Angle offset for the left and right cameras. It's and estimation of the
# additional steering angle (normalized [-1,1]) that we would have to steer
# if the center camera was in the position of the left or right one
ANGLE_OFFSET = 0.1

# Batch size
BATCH_SIZE = 64

def image_generator(log_file_csv, batch_size,
                    img_shape = preprocess_input.FINAL_IMG_SHAPE):
    """ Provides a batch of images from a log file. The main advantage
        of using a generator is that we do not need to read the whole log file,
        only one batch at a time, so it will fit in RAM.
        This function also generates extended data on the fly. """
    log_idx = 0
    n_rows_to_process = int(batch_size/N_IMG_PER_ROW)

    n_log_img = len(log_file_csv)

    # Pre-allocate data
    x = np.ndarray(shape=(batch_size, img_shape[0], img_shape[1], img_shape[2]))
    y = np.ndarray(shape=(batch_size,))

    shuffle_idx = np.arange(0, n_log_img)

    while 1:
        #if log_idx  < n_rows_to_process:
            # shuffle
            #np.random.shuffle(shuffle_idx)

        for j in range(0, n_rows_to_process):
            log_idx  = (log_idx  + 1) % n_log_img

            # Compute shuffled idx
            i_shuffle = shuffle_idx[log_idx]

            # Read center, left and right images from log file
            x_i_c = cv2.imread(log_file_csv.iloc[i_shuffle][0])
            x_i_l = cv2.imread(log_file_csv.iloc[i_shuffle][1])
            x_i_r = cv2.imread(log_file_csv.iloc[i_shuffle][2])

            # Read steering angles. Add ANGLE_OFFSET to left/right cameras
            y_i_c = float(log_file_csv.iloc[i_shuffle][3])
            y_i_l = y_i_c + ANGLE_OFFSET
            y_i_r = y_i_c - ANGLE_OFFSET

            # Preprocess images
            x_i_c = np.squeeze(preprocess_input.main(np.reshape(x_i_c, (1,) + x_i_c.shape)))
            x_i_l = np.squeeze(preprocess_input.main(np.reshape(x_i_l, (1,) + x_i_l.shape)))
            x_i_r = np.squeeze(preprocess_input.main(np.reshape(x_i_r, (1,) + x_i_r.shape)))

            # Add to batch
            i = N_IMG_PER_ROW * j
            x[i    ] = x_i_c
            x[i + 1] = x_i_l
            x[i + 2] = x_i_r

            y[i    ] =  y_i_c
            y[i + 1] =  y_i_l
            x[i + 2] =  y_i_r

            # Add flipped version of center camera
            x[i + 3] = cv2.flip(x_i_c, 1)
            y[i + 3] = -y_i_c

        yield (x, y)


def normalize(X):
    """ Normalizes the input between -0.5 and 0.5 """
    return X / 255. - 0.5


def define_model():
    """ Defines the network architecture, following Nvidia's example on:
        http://images.nvidia.com/content/tegra/automotive/images/2016/solutions/pdf/end-to-end-dl-using-px.pdf """

    # Parameters
    input_shape = preprocess_input.FINAL_IMG_SHAPE

    weight_init='glorot_uniform'
    padding = 'valid'
    activation = 'relu'
    dropout_prob = 0.5

    # Define model
    model = Sequential()

    model.add(Lambda(normalize, input_shape=input_shape, output_shape=input_shape))

    model.add(Convolution2D(24, 5, 5,
                            border_mode=padding,
                            init = weight_init, subsample = (2, 2)))
    model.add(Activation(activation))
    model.add(Convolution2D(36, 5, 5,
                            border_mode=padding,
                            init = weight_init, subsample = (2, 2)))
    model.add(Activation(activation))
    model.add(Convolution2D(48, 5, 5,
                            border_mode=padding,
                            init = weight_init, subsample = (2, 2)))
    model.add(Activation(activation))
    model.add(Convolution2D(64, 3, 3,
                            border_mode=padding,
                            init = weight_init, subsample = (1, 1)))
    model.add(Activation(activation))
    model.add(Convolution2D(64, 3, 3,
                            border_mode=padding,
                            init = weight_init, subsample = (1, 1)))

    model.add(Flatten())
    model.add(Dropout(dropout_prob))
    model.add(Activation(activation))

    model.add(Dense(100, init = weight_init))
    model.add(Dropout(dropout_prob))
    model.add(Activation(activation))

    model.add(Dense(50, init = weight_init))
    model.add(Dropout(dropout_prob))
    model.add(Activation(activation))

    model.add(Dense(10, init = weight_init))
    model.add(Dropout(dropout_prob))
    model.add(Activation(activation))

    model.add(Dense(1, init = weight_init, name = 'output'))

    model.summary()

    # Compile it
    model.compile(loss = 'mse', optimizer = Adam(lr = 0.001))

    return model


def train_model(model, n_epochs, train_csv, val_csv):
    """ Trains model """
    print('Training model...')

    batch_size = BATCH_SIZE

    n_train_samples = math.ceil(N_IMG_PER_ROW * len(train_csv)/batch_size) * batch_size
    n_val_samples = math.ceil(N_IMG_PER_ROW * len(val_csv)/batch_size) * batch_size

    gen_train = image_generator(train_csv, batch_size)
    gen_val = image_generator(val_csv, batch_size)

    model.fit_generator(generator = gen_train,
                        samples_per_epoch = n_train_samples,
                        validation_data = gen_val,
                        nb_val_samples = n_val_samples,
                        nb_epoch = n_epochs,
                        verbose = 1)


def save_model(out_dir, model):
    """ Saves model (json) and weights (h5) to disk """
    print('Saving model in %s...' % out_dir)

    # Create directory if needed
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Save model
    model_json = model.to_json()
    with open(os.path.join(out_dir, 'model.json'), 'w+') as f:
        json.dump(model_json, f)

    # Save weights
    model.save_weights(os.path.join(out_dir, 'model.h5'))


def evaluate_model(model, test_csv):
    """ Evaluates the model on test data, printing out the loss """
    print('Evaluating model on test set...')
    batch_size = BATCH_SIZE
    n_test_samples = math.ceil(N_IMG_PER_ROW * len(test_csv)/batch_size) * batch_size

    gen_test = image_generator(test_csv, batch_size)
    score = model.evaluate_generator(gen_test, n_test_samples)

    print(score)


def split_training_data(csv_data, train_ratio, val_ratio):
    """ Split input log file (CSV) into train, validation and test sets,
        according to train_ratio and val_ratio """
    assert train_ratio + val_ratio < 1.0

    n_total = len(csv_data)
    n_train = int(math.ceil(n_total * train_ratio))
    n_val = int(math.ceil(n_total * val_ratio))

    idx = np.arange(0, n_total)
    np.random.shuffle(idx)

    train_csv = csv_data.iloc[idx[0:n_train]]
    val_csv = csv_data.iloc[idx[n_train : n_train + n_val]]
    test_csv = csv_data.iloc[idx[n_train + n_val:]]

    return train_csv, val_csv, test_csv

def build_model(log_file_path, n_epochs):
    """ Builds and trains the network given the input data in train_dir """
    # Read CSV file with pandas
    data = pd.read_csv(log_file_path, sep=', ')

    # Split into train, validation and test sets
    train_csv, val_csv, test_csv = split_training_data(data, 0.8, 0.1)
    print ('Train set: %d, validation set: %d, test set: %d' %
            (len(train_csv), len(val_csv), len(test_csv)))

    # Build and train the network
    model = define_model()
    train_model(model, n_epochs, train_csv, val_csv)

    # Evaluate model on test data
    evaluate_model(model, test_csv)

    return model


def parse_input():
    """ Sets up the required input arguments and parses them """
    parser = argparse.ArgumentParser()

    parser.add_argument('log_file', help='CSV file of log data')
    parser.add_argument('-e, --n_epochs', dest='n_epochs',
                        help='number of training epochs', metavar='',
                        type=int, default=5)
    parser.add_argument('-o, --out_dir', dest='out_dir', metavar='',
                        default=time.strftime("%Y%m%d_%H%M%S"),
                        help='directory where the model is stored')

    return parser.parse_args()


def main():
    """ Main function """
    # Get input
    args = parse_input()

    # Build a model
    model = build_model(args.log_file, args.n_epochs)

    # Save model
    save_model(args.out_dir, model)

    print('Finished!')

if __name__ == '__main__':
    main()
