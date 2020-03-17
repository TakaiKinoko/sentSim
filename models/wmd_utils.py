"""
Utility static functions
"""

import pulp
from collections import defaultdict
from scipy.spatial.distance import euclidean
from gensim.utils import tokenize
from gensim.parsing.preprocessing import remove_stopwords
from itertools import product, combinations
from models.utils import tokens_to_fracdict, clean_sentences


def word_mover_distance_probspec(first_sent_tokens, second_sent_tokens, wvmodel, lpFile=None):
    """

    :param first_sent_tokens:
    :param second_sent_tokens:
    :param wvmodel:
    :param lpFile:
    :return:
    """
    all_tokens = set()
    for t in list(set(first_sent_tokens + second_sent_tokens)):
        try:
            wvmodel[t]
            all_tokens.add(t)
        except KeyError:
            pass

    # all_tokens = list(set(first_sent_tokens+second_sent_tokens))
    """
    wordvecs = {}
    for token in all_tokens:
        try:
            vec = wvmodel[token]
        except KeyError:
            vec = None
        if vec is not None:
            wordvecs[token] = vec
    """
    wordvecs = {token: wvmodel[token] for token in all_tokens}

    first_sent_buckets = tokens_to_fracdict(set(first_sent_tokens).intersection(all_tokens))
    second_sent_buckets = tokens_to_fracdict(set(second_sent_tokens).intersection(all_tokens))

    T = pulp.LpVariable.dicts('T_matrix', list(product(all_tokens, all_tokens)), lowBound=0)

    prob = pulp.LpProblem('WMD', sense=pulp.LpMinimize)
    prob += pulp.lpSum([T[token1, token2] * euclidean(wordvecs[token1], wordvecs[token2])
                        for token1, token2 in product(all_tokens, all_tokens)])
    for token2 in second_sent_buckets:
        prob += pulp.lpSum([T[token1, token2] for token1 in first_sent_buckets]) == second_sent_buckets[token2]
    for token1 in first_sent_buckets:
        prob += pulp.lpSum([T[token1, token2] for token2 in second_sent_buckets]) == first_sent_buckets[token1]

    if lpFile != None:
        prob.writeLP(lpFile)

    prob.solve()

    return prob


def word_mover_distance(first_sent_tokens, second_sent_tokens, wvmodel, lpFile=None):
    """

    :param first_sent_tokens:
    :param second_sent_tokens:
    :param wvmodel:
    :param lpFile:
    :return:
    """
    prob = word_mover_distance_probspec(first_sent_tokens, second_sent_tokens, wvmodel, lpFile=lpFile)
    return pulp.value(prob.objective)


def get_token_list(query_string):
    """

    :param query_string:
    :return:
    """
    return list(tokenize(remove_stopwords(query_string)))


def append_to_sentences(sentences, string):
    """

    :param sentences:
    :param string:
    :return:
    """
    sentences.append(list(tokenize(string)))


def compare_all_pairs(sentences, w2vmodel):
    """
    Compute the word mover distance between all possible sentence pairs from a list of sentences
    :param sentences:
    :param w2vmodel:
    :return:
    """
    for s1, s2 in combinations(sentences, 2):
        # get similarity between s1 and s2
        prob = word_mover_distance_probspec(s1, s2, w2vmodel)
        print(s1)
        print(s2)
        print(pulp.value(prob.objective))


def get_match(target, candidates, w2vmodel):
    """
    Given a word mover model, a target sentence and a list of candidates, return a sentence from candidates that matches
    the target most closely, meaning:
        min(word_mover_distance(target, s) for all s in candidates)

    :param target: a String
    :param candidates:
    :param w2vmodel:
    :return:
    """
    # parse target string into a list of tokens
    new_s1 = get_token_list(target)
    scores = {candidates.index(s): pulp.value(word_mover_distance_probspec(new_s1, s, w2vmodel).objective) for
              s in
              candidates}
    return candidates[min(scores, key=scores.get)]


"""
def get_match_from_dict(target_list, candidates_dict, wm_model):

    Given a word mover model, a target sentence and a list of candidates, return a sentence from candidates that matches
    the target most closely, meaning:
        min(word_mover_distance(target, s) for all s in candidates)

    :param target_list: a list of tokens
    :param candidates_dict: a dict from ID to list of tokens
    :param wm_model:
    :return:

    # a dict mapping sentence id to a list of scores
    scores_dict = {id: [] for id in candidates_dict.keys()}
    #

    # heapify the lists


    # parse target string into a list of tokens
    scores = {k: pulp.value(word_mover_distance_probspec(target_list, candidates_dict[k], wm_model.w2vmodel).objective) for
              k in
              candidates_dict.keys()}
    #TODO generate a cartesian product of all pairs, compute and store the score in a table -- WHAT IS USED ABOVE IS EXTREMELY INEFFICIENT
    # use min-heap to get the key to the second smallest wmd -- the smallest is itself
    import heapq
    return heapq.nsmallest(2, scores, key=scores.get)[-1]
    # return min(scores, key=scores.get) # return the key
    """


def compute_scores_batch(candidates_dict, w2vmodel):
    """
    Given a dict from sentence ID to sentence token list, return a dict that maps from any sentence of ID1 in the
    candidates_dict to a dict that maps all sentence of ID2 that is not ID1 to a float that represents the
    word mover distance between ID1 and ID2.

    :param candidates_dict: a dict of sentences mapping its id to its list of tokens
    :param w2vmodel: word mover model
    :return: a dict mapping sentence id to a list of scores (wmd) with all sentences from the candidates_dict
            except for itself
    """
    # a dict mapping sentence id to a list of scores
    scores_dict = {id: {} for id in candidates_dict.keys()}

    total_cnt = len(candidates_dict)
    cnt = 0  # counter for reporting progress
    for key1 in candidates_dict.keys():
        for key2 in candidates_dict.keys():
            if key1 == key2:
                continue
            else:
                scores_dict[key1][key2] = pulp.value(word_mover_distance_probspec(
                    candidates_dict[key1], candidates_dict[key2], w2vmodel).objective)
        cnt += 1
        # report progress per ten sentences processed
        if cnt % 10 == 0:
            print("wmd computation completed: %.2f" % (cnt / total_cnt * 100))
    return scores_dict
