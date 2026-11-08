export function validateLogin(username: string, password: string) {
  if (!username.trim()) return {field: "username" as const, message: "Введите логин"};
  if (!password) return {field: "password" as const, message: "Введите пароль"};
  return null;
}

/** Never surface arbitrary response bodies (validation payloads can contain input). */
export function loginFailureText(status?: number) {
  if (status === 401) return "Неверный логин или пароль. Проверьте данные и попробуйте ещё раз.";
  if (status === 0) return "Не удалось связаться с сервером. Проверьте соединение и повторите попытку.";
  if (status === 429) return "Слишком много попыток входа. Подождите и попробуйте ещё раз.";
  return "Не удалось войти. Повторите попытку позже.";
}
