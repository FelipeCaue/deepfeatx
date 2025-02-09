# AUTOGENERATED! DO NOT EDIT! File to edit: 00_image.ipynb (unless otherwise specified).

__all__ = ['download_dataset', 'ImageFeatureExtractor']

# Cell
#hide_output
# All Imports
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from io import BytesIO
from PIL import Image
from PIL import ImageFile
import glob
ImageFile.LOAD_TRUNCATED_IMAGES = True #https://stackoverflow.com/questions/12984426/python-pil-ioerror-image-file-truncated-with-big-images
import os

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Flatten, Dense, GlobalAveragePooling2D
from tensorflow.keras.applications import resnet50
#from tensorflow.keras.applications import efficientnet
from tensorflow.keras.preprocessing.image import ImageDataGenerator

import torchvision.transforms as transforms

# All Parameters


# Functions and classes
def download_dataset(data_url, zip_filename):
    try: # Then try downloading and unzipping it
        print("Downloading Dataset...")
        os.system(f"wget {data_url}")

        print("Unzipping Dataset")
        if 'tgz' in zip_filename:
            os.system(f"tar -xvzf {zip_filename}")
        else:
            os.system(f"unzip {zip_filename}")

        print("Removing .zip file")
        os.system(f"rm {zip_filename}")
    except Exception as e: # If there's an error, ask to download manually
        print(f"Something went wrong. Please download the dataset manually at {data_url}")
        print(f'The following exception was thrown:\n{e}')


class ImageFeatureExtractor():
    def __init__(self, model_name='resnet', target_shape=(224, 224, 3)):
        self.target_shape = target_shape
        self.model = self._get_model(model_name)
        self.model_name = model_name

    def _center_crop_img(self, img, size=224): #using pytorch as it gives more freedom in the transformations
        tr = transforms.Compose([
            transforms.Resize(size),
            transforms.CenterCrop(size),
        ])
        return tr(img)

    def _preprocess_img(self, img):
        img=self._center_crop_img(img, size=self.target_shape[0])

        # Convert to a Numpy array
        img_np = np.asarray(img)

        # Reshape by adding 1 in the beginning to be compatible as input of the model
        img_np = img_np[None] # https://docs.scipy.org/doc/numpy/reference/arrays.indexing.html#numpy.newaxis

        # Prepare the image for the model
        img_np = self.preprocess_input(img_np)

        return img_np

    def _get_model(self, model_name):
        if model_name=='resnet':
            self.preprocess_input = resnet50.preprocess_input

            base_model = resnet50.ResNet50(include_top=False,
                                           input_shape=self.target_shape)

            for layer in base_model.layers:
                layer.trainable=False

            model = Sequential([base_model,
                                GlobalAveragePooling2D()])

            return model

        return None

    def _get_img_gen_from_df(self, dataframe, batch_size=32):

        datagen = ImageDataGenerator(preprocessing_function=self.preprocess_input)

        gen = datagen.flow_from_dataframe(dataframe,
                                          batch_size=batch_size,
                                          target_size=self.target_shape[:2],
                                          class_mode=None,
                                          shuffle=False)
        return gen

    def _get_img_gen(self, folder_path, batch_size=32):
        datagen = ImageDataGenerator(preprocessing_function=self.preprocess_input)
        gen = datagen.flow_from_directory(folder_path,
                                          batch_size=batch_size,
                                          target_size=self.target_shape[:2],
                                          class_mode='sparse',
                                          shuffle=False)
        return gen

    def _assert_df_size(self, dataframe):
        assert len(dataframe)>0, "Folder not found or does not have images. If there's one folder per class, please make sure to set classes_as_folders to True"

    def read_img_url(self, url, center_crop=True):
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        if center_crop:
            img = self._center_crop_img(img, size=self.target_shape[0])
        return img

    def read_img_path(self, img_path, center_crop=True):
        img = image.load_img(img_path)
        if center_crop:
            img = self._center_crop_img(img, size=self.target_shape[0])
        return img

    def url_to_vector(self, url):
        img = self.read_img_url(url)
        vector = self.img_to_vector(img)
        return vector

    def img_path_to_vector(self, img_path):
        img = self.read_img_path(img_path)
        vector = self.img_to_vector(img)
        return vector

    def img_to_vector(self, img):
        img_np = self._preprocess_img(img)
        vector = self.model.predict(img_np)
        return vector

    def _get_gen(self, classes_as_folders, directory, batch_size):
        if classes_as_folders:
            gen = self._get_img_gen(directory, batch_size)
        else:
            filepaths = glob.glob(directory+'/*.*')
            self.dataframe=pd.DataFrame(filepaths,
                                        columns=['filename'])
            self._assert_df_size(self.dataframe)
            gen = self._get_img_gen_from_df(self.dataframe,
                                            batch_size)
        return gen

    def _vectors_to_df(self, all_vectors, classes_as_folders, export_class_names):
        vectors_df=pd.DataFrame(all_vectors)
        vectors_df.insert(loc=0, column='filepaths', value=self.gen.filepaths)
        if classes_as_folders and export_class_names:
            vectors_df.insert(loc=1, column='classes', value=self.gen.classes)
            id_to_class = {v: k for k, v in self.gen.class_indices.items()}
            vectors_df.classes=vectors_df.classes.apply(lambda x: id_to_class[x])
        return vectors_df

    def extract_features_from_directory(self,
                                        directory,
                                        batch_size=32,
                                        classes_as_folders=True,
                                        export_class_names=False,
                                        export_vectors_as_df=True):
        # Get image generator
        self.gen = self._get_gen(classes_as_folders, directory, batch_size)

        # Extract features into vectors
        self.all_vectors=self.model.predict(self.gen, verbose=1)

        # Either return vectors or everything as dataframes
        if not export_vectors_as_df:
            return self.all_vectors
        else:
            vectors_df = self._vectors_to_df(self.all_vectors, classes_as_folders, export_class_names)
            return vectors_df

    def vectors_from_folder_list(self, folder_list):
        df_list = []
        for folder_path in folder_list:
            df=self.img_folder_to_vectors(folder_path)
            df_list.append(df)
        return pd.concat(df_list)
