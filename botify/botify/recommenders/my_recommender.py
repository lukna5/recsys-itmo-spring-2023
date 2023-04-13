import random

from .random import Random
from .recommender import Recommender
from .toppop import TopPop


class MyRecommender(Recommender):

    def __init__(self, tracks_redis, artists_redis, catalog):
        self.tracks_redis = tracks_redis
        self.fallback = Random(tracks_redis)
        self.topPop = TopPop(tracks_redis, catalog.top_tracks)
        self.artists_redis = artists_redis
        self.catalog = catalog

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        fails_to_best = 3
        min_time_not_bad_track = 0.6

        previous_track = self.tracks_redis.get(prev_track)
        if previous_track is None:
            # Рекомендуем топ треки, если ничего не знаем
            return self.topPop.recommend_next(user, prev_track, prev_track_time)

        previous_track = self.catalog.from_bytes(previous_track)
        artist = previous_track.artist

        #1
        # Обновляем заинтересованность пользователя артистом, а также его любимого артиста
        if user in self.catalog.users_loving_artists:
            if artist in self.catalog.users_loving_artists[user]:
                score, count = self.catalog.users_loving_artists[user][artist]
                new_median = (score * count + prev_track_time) / (count + 1)
                self.catalog.users_loving_artists[user][artist] = (new_median, count + 1)
                if self.catalog.favourite_artist[user][0] == artist:
                    self.catalog.favourite_artist[user] = (artist, prev_track, new_median)
                else:
                    if self.catalog.favourite_artist[user][2] <= new_median:
                        self.catalog.favourite_artist[user] = (artist, prev_track, new_median)
            else:
                if self.catalog.favourite_artist[user][2] <= prev_track_time:
                    self.catalog.favourite_artist[user] = (artist, prev_track, prev_track_time)
                self.catalog.users_loving_artists[user][artist] = (prev_track_time, 1)
        else:
            self.catalog.favourite_artist[user] = (artist, prev_track, prev_track_time)
            self.catalog.users_loving_artists[user] = {artist: (prev_track_time, 1)}

        #2
        # Проверка на, то, что данный трек на зашел пользователю и анализ последнего неплохого трека
        if user in self.catalog.last_not_bad_track:
            if prev_track_time >= min_time_not_bad_track:
                self.catalog.fails[user] = 0
                self.catalog.last_not_bad_track[user] = (prev_track, prev_track_time)
            else:
                if user in self.catalog.fails:
                    self.catalog.fails[user] += 1
                else:
                    self.catalog[user] = 1
                prev_track, prev_track_time = self.catalog.last_not_bad_track[user]
        else:
            self.catalog.fails[user] = 0 if prev_track_time < min_time_not_bad_track else 1
            self.catalog.last_not_bad_track[user] = (prev_track, prev_track_time)

        #3
        # Анализируем количество фейлов и возвращаемся к лучшему треку, если их много
        if user in self.catalog.best_track:
            best_track, best_time = self.catalog.best_track[user]
            if best_time <= prev_track_time:
                self.catalog.best_track[user] = (prev_track, prev_track_time)
            elif self.catalog.fails[user] >= fails_to_best:
                prev_track = best_track
                prev_track_time = best_time
        else:
            self.catalog.best_track[user] = (prev_track, prev_track_time)

        # Фиксируем трек, на основе которого будем рекомендовать
        previous_track = self.tracks_redis.get(prev_track)
        if previous_track is None:
            # Рекомендуем топ треки, если ничего не знаем
            return self.topPop.recommend_next(user, prev_track, prev_track_time)

        previous_track = self.catalog.from_bytes(previous_track)
        artist = previous_track.artist
        recommendations = previous_track.recommendations

        #4
        if not recommendations:
            if user not in self.catalog.favourite_artist:
                return self.fallback.recommend_next(user, prev_track, prev_track_time)

            favourite_artist, last_track_from_favourite_artist, _ = self.catalog.favourite_artist[user]
            # Если не знаем, что рекомендовать, давайте давать трек любимого артиста
            artist_data = self.artists_redis.get(favourite_artist)
            if artist_data is not None:
                artist_tracks = self.catalog.from_bytes(artist_data)
            else:
                return self.fallback.recommend_next(user, prev_track, prev_track_time)

            shuffled = list(artist_tracks)
            if len(shuffled) == 1:
                return self.fallback.recommend_next(user, prev_track, prev_track_time)
            random.shuffle(shuffled)
            if shuffled[0] == last_track_from_favourite_artist:
                return shuffled[1]
            return shuffled[0]

        # Попытка брать самые популярные треки среди рекомендованных
        # for track_top in self.catalog.top_tracks:
        #     for track_rec in recommendations:
        #         if track_rec == track_top:
        #             return track_rec

        # Попытка брать треки любимого артиста среди рекомендованных
        # recommended_from_cur_artist = []
        # if self.catalog.users_loving_artists[user][artist][0] > 0.75:
        #     for track in recommendations:
        #         cur_track = self.catalog.from_bytes(self.tracks_redis.get(track))
        #         if cur_track.artist == artist:
        #             recommended_from_cur_artist.append(track)
        #     if len(recommended_from_cur_artist) > 0:
        #         recommendations = recommended_from_cur_artist

        shuffled = list(recommendations)
        random.shuffle(shuffled)
        return shuffled[0]
