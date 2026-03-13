// Конфиг Babel для Expo / React Native
// Обязателен для компиляции JSX и современного JS на телефоне
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
  };
};
