# MIT License
#
# Copyright (C) IBM Corporation 2018
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
This module implements abstract base classes defining to properties for all classifiers.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import abc
from typing import List, Optional, Tuple, Union, TYPE_CHECKING

import numpy as np

from art.utils import check_and_transform_label_format

if TYPE_CHECKING:
    from art.config import CLIP_VALUES_TYPE, PREPROCESSING_TYPE
    from art.data_generators import DataGenerator
    from art.defences import Preprocessor, Postprocessor
    from art.metrics.verification_decisions_trees import Tree


class input_filter(abc.ABCMeta):
    """
    Metaclass to ensure that inputs are ndarray for all of the subclass generate and extract calls.
    """

    def __init__(cls, name, bases, clsdict):
        """
        This function overrides any existing generate or extract methods with a new method that
        ensures the input is an ndarray. There is an assumption that the input object has implemented
        __array__ with np.array calls.
        """

        def make_replacement(fdict, func_name, has_y):
            """
            This function overrides creates replacement functions dynamically.
            """

            def replacement_function(self, *args, **kwargs):
                if len(args) > 0:
                    lst = list(args)

                if "x" in kwargs:
                    if not isinstance(kwargs["x"], np.ndarray):
                        kwargs["x"] = np.array(kwargs["x"])
                else:
                    if not isinstance(args[0], np.ndarray):
                        lst[0] = np.array(args[0])

                if "y" in kwargs:
                    if kwargs["y"] is not None and not isinstance(
                        kwargs["y"], np.ndarray
                    ):
                        kwargs["y"] = np.array(kwargs["y"])
                elif has_y:
                    if not isinstance(args[1], np.ndarray):
                        lst[1] = np.array(args[1])

                if len(args) > 0:
                    args = tuple(lst)
                return fdict[func_name](self, *args, **kwargs)

            replacement_function.__doc__ = fdict[func_name].__doc__
            replacement_function.__name__ = "new_" + func_name
            return replacement_function

        replacement_list_no_y = ["predict", "get_activations", "class_gradient"]
        replacement_list_has_y = ["fit", "loss_gradient"]

        for item in replacement_list_no_y:
            if item in clsdict:
                new_function = make_replacement(clsdict, item, False)
                setattr(cls, item, new_function)
        for item in replacement_list_has_y:
            if item in clsdict:
                new_function = make_replacement(clsdict, item, True)
                setattr(cls, item, new_function)


class Classifier(abc.ABC, metaclass=input_filter):
    """
    Base class defining the minimum classifier functionality and is required for all classifiers. A classifier of this
    type can be combined with black-box attacks.
    """

    def __init__(
        self,
        clip_values: Optional["CLIP_VALUES_TYPE"] = None,
        preprocessing_defences: Union[
            "Preprocessor", List["Preprocessor"], None
        ] = None,
        postprocessing_defences: Union[
            "Postprocessor", List["Postprocessor"], None
        ] = None,
        preprocessing: Optional["PREPROCESSING_TYPE"] = None,
        **kwargs
    ) -> None:
        """
        Initialize a `Classifier` object.

        :param clip_values: Tuple of the form `(min, max)` of floats or `np.ndarray` representing the minimum and
               maximum values allowed for features. If floats are provided, these will be used as the range of all
               features. If arrays are provided, each value will be considered the bound for a feature, thus
               the shape of clip values needs to match the total number of features.
        :param preprocessing_defences: Preprocessing defence(s) to be applied by the classifier.
        :param postprocessing_defences: Postprocessing defence(s) to be applied by the classifier.
        :param preprocessing: Tuple of the form `(subtractor, divider)` of floats or `np.ndarray` of values to be
               used for data preprocessing. The first value will be subtracted from the input. The input will then
               be divided by the second one.
        """
        from art.defences.preprocessor.preprocessor import Preprocessor
        from art.defences.postprocessor.postprocessor import Postprocessor

        self._clip_values = clip_values
        if clip_values is not None:
            if len(clip_values) != 2:
                raise ValueError(
                    "`clip_values` should be a tuple of 2 floats or arrays containing the allowed data range."
                )
            if np.array(clip_values[0] >= clip_values[1]).any():
                raise ValueError("Invalid `clip_values`: min >= max.")

        self.preprocessing_defences: Union[List[Preprocessor], None]
        if isinstance(preprocessing_defences, Preprocessor):
            self.preprocessing_defences = [preprocessing_defences]
        else:
            self.preprocessing_defences = preprocessing_defences

        self.postprocessing_defences: Union[List[Postprocessor], None]
        if isinstance(postprocessing_defences, Postprocessor):
            self.postprocessing_defences = [postprocessing_defences]
        else:
            self.postprocessing_defences = postprocessing_defences

        if preprocessing is not None and len(preprocessing) != 2:
            raise ValueError(
                "`preprocessing` should be a tuple of 2 floats with the values to subtract and divide"
                "the model inputs."
            )
        self.preprocessing = preprocessing

        super().__init__()

    @abc.abstractmethod
    def predict(
        self, x: np.ndarray, **kwargs
    ) -> np.ndarray:  # lgtm [py/inheritance/incorrect-overridden-signature]
        """
        Perform prediction of the classifier for input `x`.

        :param x: Features in array of shape `(nb_samples, nb_features)` or `(nb_samples, nb_pixels_1, nb_pixels_2,
                  nb_channels)` or `(nb_samples, nb_channels, nb_pixels_1, nb_pixels_2)`.
        :return: Array of predictions of shape `(nb_inputs, nb_classes)`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def fit(
        self, x: np.ndarray, y: np.ndarray, **kwargs
    ) -> None:  # lgtm [py/inheritance/incorrect-overridden-signature]
        """
        Fit the classifier using the training data `(x, y)`.

        :param x: Features in array of shape `(nb_samples, nb_features)` or `(nb_samples, nb_pixels_1, nb_pixels_2,
                  nb_channels)` or `(nb_samples, nb_channels, nb_pixels_1, nb_pixels_2)`.
        :param y: Target values (class labels) one-hot-encoded of shape `(nb_samples, nb_classes)` or indices of shape
                  `(nb_samples,)`.
        :param kwargs: Dictionary of framework-specific arguments.
        """
        raise NotImplementedError

    @property
    def clip_values(self) -> Optional["CLIP_VALUES_TYPE"]:
        """
        :return: Tuple of form `(min, max)` containing the minimum and maximum values allowed for the input features.
        """
        return self._clip_values

    @property
    def input_shape(self) -> Tuple[int, ...]:
        """
        Return the shape of one input.

        :return: Shape of one input for the classifier.
        """
        return self._input_shape  # type: ignore

    @abc.abstractmethod
    def nb_classes(self) -> int:
        """
        Return the number of output classes.

        :return: Number of classes in the data.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, filename: str, path: Optional[str] = None) -> None:
        """
        Save a model to file specific to the backend framework.

        :param filename: Name of the file where to save the model.
        :param path: Path of the directory where to save the model. If no path is specified, the model will be stored in
                     the default data location of ART at `ART_DATA_PATH`.
        """
        raise NotImplementedError

    def _apply_preprocessing(
        self, x: np.ndarray, y: Optional[np.ndarray], fit: bool
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply all defences and preprocessing operations on the inputs `(x, y)`. This function has to be applied to all
        raw inputs `(x, y)` provided to the classifier.

        :param x: Features, where first dimension is the number of samples.
        :param y: Target values (class labels), where first dimension is the number of samples.
        :param fit: `True` if the defences are applied during training.
        :return: Value of the data after applying the defences.
        """
        y = check_and_transform_label_format(y, self.nb_classes())
        x_preprocessed, y_preprocessed = self._apply_preprocessing_defences(
            x, y, fit=fit
        )
        x_preprocessed = self._apply_preprocessing_standardisation(x_preprocessed)
        return x_preprocessed, y_preprocessed

    def _apply_preprocessing_defences(
        self, x: np.ndarray, y: np.ndarray, fit: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply all preprocessing defences of the classifier on the raw inputs `(x, y)`. This function is intended to
        only be called from function `_apply_preprocessing`.

        :param x: Features, where first dimension is the number of samples.
        :param y: Target values (class labels), where first dimension is the number of samples.
        :param fit: `True` if the function is call before fit/training and `False` if the function is called before a
                    predict operation.
        :return: Arrays for `x` and `y` after applying the defences.
        """
        if self.preprocessing_defences is not None:
            for defence in self.preprocessing_defences:
                if fit:
                    if defence.apply_fit:
                        x, y = defence(x, y)
                else:
                    if defence.apply_predict:
                        x, y = defence(x, y)

        return x, y

    def _apply_preprocessing_standardisation(self, x: np.ndarray) -> np.ndarray:
        """
        Apply standardisation to input data `x`.

        :param x: Input data, where first dimension is the number of samples.
        :return: Array for `x` with the standardized data.
        :raises TypeError: If the input array has an unsupported `dtype`.
        """
        if x.dtype in [np.uint8, np.uint16, np.uint32, np.uint64]:
            raise TypeError(
                "The data type of input data `x` is {} and cannot represent negative values. Consider "
                "changing the data type of the input data `x` to a type that supports negative values e.g. "
                "np.float32.".format(x.dtype)
            )

        if self.preprocessing is not None:
            sub, div = self.preprocessing
            sub = np.asarray(sub, dtype=x.dtype)
            div = np.asarray(div, dtype=x.dtype)

            res = x - sub
            res = res / div

        else:
            res = x

        return res

    def _apply_postprocessing(self, preds: np.ndarray, fit: bool) -> np.ndarray:
        """
        Apply all defences operations on model output.

        :param preds: model output to be postprocessed.
        :param fit: `True` if the defences are applied during training.
        :return: Postprocessed model output.
        """
        post_preds = preds.copy()
        if self.postprocessing_defences is not None:
            for defence in self.postprocessing_defences:
                if fit:
                    if defence.apply_fit:
                        post_preds = defence(post_preds)
                else:
                    if defence.apply_predict:
                        post_preds = defence(post_preds)

        return post_preds

    def __repr__(self):
        class_name = self.__class__.__name__
        attributes = {
            (k[1:], v) if k[0] == "_" else (k, v) for (k, v) in self.__dict__.items()
        }
        attributes = ["{}={}".format(k, v) for (k, v) in attributes]
        repr_string = class_name + "(" + ", ".join(attributes) + ")"
        return repr_string


class ClassifierNeuralNetwork(abc.ABC, metaclass=input_filter):
    """
    Base class defining additional classifier functionality required for neural network classifiers. This base class
    has to be mixed in with class `Classifier` to extend the minimum classifier functionality.
    """

    def __init__(self, channel_index: Optional[int] = None, **kwargs) -> None:
        """
        Initialize a `ClassifierNeuralNetwork` object.

        :param channel_index: Index of the axis in input (feature) array `x` representing the color channels.
        """
        self._channel_index = channel_index
        super().__init__()

    @abc.abstractmethod
    def predict(self, x: np.ndarray, batch_size: int = 128, **kwargs) -> np.ndarray:
        """
        Perform prediction of the classifier for input `x`.

        :param x: Features in array of shape `(nb_samples, nb_features)` or `(nb_samples, nb_pixels_1, nb_pixels_2,
                  nb_channels)` or `(nb_samples, nb_channels, nb_pixels_1, nb_pixels_2)`.
        :param batch_size: The batch size used for evaluating the classifier's `model`.
        :return: Array of predictions of shape `(nb_inputs, nb_classes)`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        batch_size: int = 128,
        nb_epochs: int = 20,
        **kwargs
    ) -> None:
        """
        Fit the classifier on the training set `(x, y)`.

        :param x: Features in array of shape `(nb_samples, nb_features)` or `(nb_samples, nb_pixels_1, nb_pixels_2,
                  nb_channels)` or `(nb_samples, nb_channels, nb_pixels_1, nb_pixels_2)`.
        :param y: Target values (class labels) one-hot-encoded of shape `(nb_samples, nb_classes)` or indices of shape
                  `(nb_samples,)`.
        :param batch_size: The batch size used for evaluating the classifier's `model`.
        :param nb_epochs: Number of epochs to use for training.
        :param kwargs: Dictionary of framework-specific arguments.
        """
        raise NotImplementedError

    def fit_generator(
        self, generator: "DataGenerator", nb_epochs: int = 20, **kwargs
    ) -> None:
        """
        Fit the classifier using `generator` yielding training batches as specified. Framework implementations can
        provide framework-specific versions of this function to speed-up computation.

        :param generator: Batch generator providing `(x, y)` for each epoch.
        :param nb_epochs: Number of epochs to use for training.
        :param kwargs: Dictionary of framework-specific arguments.
        """
        for _ in range(nb_epochs):
            for _ in range(int(generator.size / generator.batch_size)):  # type: ignore
                x, y = generator.get_batch()

                # Apply preprocessing and defences
                x_preprocessed, y_preprocessed = self._apply_preprocessing(  # type: ignore
                    x, y, fit=True
                )

                # Fit for current batch
                self.fit(
                    x_preprocessed,
                    y_preprocessed,
                    nb_epochs=1,
                    batch_size=generator.batch_size,
                    **kwargs
                )

    @property
    def channel_index(self) -> Optional[int]:
        """
        :return: Index of the axis in input data containing the color channels.
        """
        return self._channel_index

    @property
    def learning_phase(self) -> Optional[bool]:
        """
        Return the learning phase set by the user for the current classifier. Possible values are `True` for training,
        `False` for prediction and `None` if it has not been set through the library. In the latter case, the library
        does not do any explicit learning phase manipulation and the current value of the backend framework is used.
        If a value has been set by the user for this property, it will impact all following computations for
        model fitting, prediction and gradients.

        :return: Value of the learning phase.
        """
        return self._learning_phase if hasattr(self, "_learning_phase") else None  # type: ignore

    @property
    def layer_names(self) -> List[str]:
        """
        Return the hidden layers in the model, if applicable.

        :return: The hidden layers in the model, input and output layers excluded.

        .. warning:: `layer_names` tries to infer the internal structure of the model.
                     This feature comes with no guarantees on the correctness of the result.
                     The intended order of the layers tries to match their order in the model, but this is not
                     guaranteed either.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_activations(
        self, x: np.ndarray, layer: Union[int, str], batch_size: int
    ) -> np.ndarray:
        """
        Return the output of the specified layer for input `x`. `layer` is specified by layer index (between 0 and
        `nb_layers - 1`) or by name. The number of layers can be determined by counting the results returned by
        calling `layer_names`.

        :param x: Input for computing the activations.
        :param layer: Layer for computing the activations.
        :param batch_size: Size of batches.
        :return: The output of `layer`, where the first dimension is the batch size corresponding to `x`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def set_learning_phase(self, train: bool) -> None:
        """
        Set the learning phase for the backend framework.

        :param train: `True` if the learning phase is training, `False` if learning phase is not training.
        """
        raise NotImplementedError

    def __repr__(self):
        name = self.__class__.__name__

        attributes = {
            (k[1:], v) if k[0] == "_" else (k, v) for (k, v) in self.__dict__.items()
        }
        attrs = ["{}={}".format(k, v) for (k, v) in attributes]
        repr_ = name + "(" + ", ".join(attrs) + ")"

        return repr_


class ClassifierGradients(abc.ABC, metaclass=input_filter):
    """
    Base class defining additional classifier functionality for classifiers providing access to loss and class
    gradients. A classifier of this type can be combined with white-box attacks. This base class has to be mixed in with
    class `Classifier` and optionally class `ClassifierNeuralNetwork` to extend the minimum classifier functionality.
    """

    @abc.abstractmethod
    def class_gradient(
        self, x: np.ndarray, label: Union[int, List[int], None] = None, **kwargs
    ) -> np.ndarray:
        """
        Compute per-class derivatives w.r.t. `x`.

        :param x: Input with shape as expected by the classifier's model.
        :param label: Index of a specific per-class derivative. If an integer is provided, the gradient of that class
                      output is computed for all samples. If multiple values as provided, the first dimension should
                      match the batch size of `x`, and each value will be used as target for its corresponding sample in
                      `x`. If `None`, then gradients for all classes will be computed for each sample.
        :return: Array of gradients of input features w.r.t. each class in the form
                 `(batch_size, nb_classes, input_shape)` when computing for all classes, otherwise shape becomes
                 `(batch_size, 1, input_shape)` when `label` parameter is specified.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def loss_gradient(self, x: np.ndarray, y: np.ndarray, **kwargs) -> np.ndarray:
        """
        Compute the gradient of the loss function w.r.t. `x`.

        :param x: Input with shape as expected by the classifier's model.
        :param y: Target values (class labels) one-hot-encoded of shape `(nb_samples, nb_classes)` or indices of shape
                  `(nb_samples,)`.
        :return: Array of gradients of the same shape as `x`.
        """
        raise NotImplementedError

    def _apply_preprocessing_gradient(
        self, x: np.ndarray, gradients: np.ndarray
    ) -> np.ndarray:
        """
        Apply the backward pass through all preprocessing operations to the gradients.

        Apply the backward pass through all preprocessing operations and defences on the inputs `(x, y)`. This function
        has to be applied to all gradients returned by the classifier.

        :param x: Features, where first dimension is the number of samples.
        :param gradients: Input gradients.
        :return: Gradients after backward step through preprocessing operations and defences.
        """
        gradients = self._apply_preprocessing_normalization_gradient(gradients)
        gradients = self._apply_preprocessing_defences_gradient(x, gradients)
        return gradients

    def _apply_preprocessing_defences_gradient(
        self, x: np.ndarray, gradients: np.ndarray, fit: bool = False
    ) -> np.ndarray:
        """
        Apply the backward pass through the preprocessing defences.

        Apply the backward pass through all preprocessing defences of the classifier on the gradients. This function is
        intended to only be called from function `_apply_preprocessing_gradient`.

        :param x: Features, where first dimension is the number of samples.
        :param gradients: Input gradient.
        :param fit: `True` if the gradient is computed during training.
        :return: Gradients after backward step through defences.
        """
        if self.preprocessing_defences is not None:  # type: ignore
            for defence in self.preprocessing_defences[::-1]:  # type: ignore
                if fit:
                    if defence.apply_fit:
                        gradients = defence.estimate_gradient(x, gradients)
                else:
                    if defence.apply_predict:
                        gradients = defence.estimate_gradient(x, gradients)

        return gradients

    def _apply_preprocessing_normalization_gradient(
        self, gradients: np.ndarray
    ) -> np.ndarray:
        """
        Apply the backward pass through standardisation of `x` to `gradients`.

        :param gradients: Input gradients.
        :return: Gradients after backward step through standardisation.
        """
        if self.preprocessing is not None:  # type: ignore
            _, div = self.preprocessing  # type: ignore
            div = np.asarray(div, dtype=gradients.dtype)
            res = gradients / div
        else:
            res = gradients

        return res


class ClassifierDecisionTree(abc.ABC):
    """
    Base class defining additional classifier functionality for decision-tree-based classifiers This base class has to
    be mixed in with class `Classifier` to extend the minimum classifier functionality.
    """

    @abc.abstractmethod
    def get_trees(self) -> List["Tree"]:
        """
        Get the decision trees.

        :return: A list of decision trees.
        """
        raise NotImplementedError


class ClassifierNeuralNetworkType(
    ClassifierNeuralNetwork, ClassifierGradients, Classifier
):
    pass


class ClassifierGradientsType(ClassifierGradients, Classifier):
    pass


class ClassifierDecisionTreeType(Classifier, ClassifierDecisionTree):
    pass
