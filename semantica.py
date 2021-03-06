import gensim
from gensim import matutils
import gensim.downloader as api

import numpy as np
from numpy import ndarray, float32, array, dot, mean, median


class Semantica:
    def __init__(self, word_count=100000):
        self.c = gensim.models.KeyedVectors.load_word2vec_format(
            api.load('word2vec-google-news-300', return_path=True), binary=True, limit=word_count)

    def unique(self, sequence):
        """Turn a list into a set, while preserving unique element order.
        """
        seen = set()
        return [x for x in sequence if not (x in seen or seen.add(x))]

    def lower_unique(self, concept_keys):
        """Turn a list of strings into a set of lowercase strings.
        """
        for i in range(len(concept_keys)):
            concept_keys[i] = concept_keys[i].lower()

        return self.unique(concept_keys)

    def to_vector(self, concept, norm_result=True):
        """Turn a concept key or vector into a concept vector.
        """
        # Extract concept vector accordingly.
        if isinstance(concept, ndarray):
            result_vector = concept
        elif isinstance(concept, str):
            result_vector = self.c.get_vector(concept)
        else:
            raise ValueError("concept should be of type str or ndarray.")

        # Optionally normalize result
        if norm_result:
            result_vector = matutils.unitvec(result_vector)

        return result_vector

    def field(self, concept, norm_concept=True, lower=True, max_concept_count=10):
        """Return the semantic field of a given concept key or vector.
        """
        # Extract concept keys most similar to concept
        field = self.c.most_similar(
            [self.to_vector(concept, norm_result=norm_concept)], topn=max_concept_count)
        field = [e[0] for e in field]

        # Optionally make concept keys lowercase and unique
        if lower:
            field = self.lower_unique(field)

        # Remove the query concept key itself from the result
        if isinstance(concept, str):
            field = [e for e in field if str(e) != str(concept)]

        return field

    def mix(self, *concepts, norm_concepts=True, norm_result=True, lower=True, return_vector=False):
        """Combine the meaning of multiple concept keys or vectors.
        """
        # Create list of vectorized concepts
        concept_vectors = []
        for concept in concepts:
            concept_vectors += [self.to_vector(concept,
                                               norm_result=norm_concepts)]

        # Compute average of vectorized concepts
        mix = array(concept_vectors).mean(axis=0).astype(float32)

        if return_vector:
            return mix

        # Compute semantic field of vector average
        results = self.field(mix, norm_concept=norm_result, lower=lower)

        # Optionally make concept keys lowercase and unique
        if lower:
            results = self.lower_unique(results)

        # Remove the query concept keys themselves from the result
        for concept in concepts:
            if isinstance(concept, str):
                results = [e for e in results if str(e) != str(concept)]

        return results

    def shift(self, source, target, norm_concepts=True, norm_result=True):
        """Return a vector which encodes a meaningful semantic shift.
        """
        # Extract concept vectors for source and target concepts
        source_vector = self.to_vector(source, norm_result=norm_concepts)
        target_vector = self.to_vector(target, norm_result=norm_concepts)

        # Compute shift
        shift = array([-1 * source_vector, target_vector]
                      ).mean(axis=0).astype(float32)

        # Optionally normalize result
        if norm_result:
            shift = matutils.unitvec(shift)

        return shift

    def span(self, start, end, steps=5, norm_concepts=False, norm_shift_result=False, norm_result=False, norm_mix_concepts=False):
        """Return an interpolation of the semantic space between two concepts.
        """
        results = []
        shift = self.shift(
            start, end, norm_concepts=norm_concepts, norm_result=norm_shift_result)

        # Append concept keys most similar to step vectors
        for step in range(1, steps + 1):
            step_key_field = self.mix(*[start, shift * (1 / (steps + 1)) * step],
                                      norm_result=norm_result, norm_concepts=norm_mix_concepts, lower=False)
            results += [*step_key_field]

        # Remove the query concept keys themselves from the result
        results = [e for e in results if e not in [start, end]]

        # Sort concept keys by location across conceptual spectrum
        results = sorted(results, key=lambda x: self.c.similarity(
            x, end) - self.c.similarity(x, start))

        # Make concept keys lowercase and unique
        results = self.lower_unique(results)

        # Add ends
        results = [start.lower(), *results, end.lower()]

        return results

    def match(self, *model, target=None):
        """Find analogies for a given conceptual model.
        """
        # Extract conceptual relations from model
        root = model[0]
        skeleton = [self.shift(root, e) for e in model[1:]]

        # Define target domain
        if target:
            target_domain = [self.to_vector(
                e[0]) for e in self.c.most_similar(target, topn=10000)]
        else:
            target_domain = self.c.vectors

        for i in range(len(target_domain)):
            match_score = []
            new_leaf_concepts = []

            # Compute concept vectors of analogy
            new_root_vector = target_domain[i]
            new_leaf_vectors = [
                self.mix(new_root_vector, skeleton[j], return_vector=True) for j in range(len(skeleton))]

            # Compute concept keys of analogy
            new_root_concept = self.c.similar_by_vector(new_root_vector)[0][0]
            new_leaf_concepts = [[e[0] for e in self.c.similar_by_vector(
                f) if e[0] not in [*model, new_root_concept]] for f in new_leaf_vectors]

            # Evaluate match through measure of alignment between relations
            for j in range(len(new_leaf_vectors)):
                match_score += [dot(self.shift(new_root_concept,
                                               new_leaf_concepts[j][k]), skeleton[j]) for k in range(len(new_leaf_concepts[j]))]

            match_score = mean(match_score)

            # Print if there's a match
            if match_score > 0.25:
                match = [new_root_concept, *new_leaf_concepts]
                print(i, match, match_score)
