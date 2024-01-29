<?php
setcookie("bw_cookie", "test", time() + (86400 * 30), "/"); // 86400 = 1 day
setcookie("bw_cookie_1", "test1", time() + (86400 * 30), "/"); // 86400 = 1 day
header("X-XSS-Protection: 0");
?>
<html>
  <body>
    <h1>Hello World!</h1>
  </body>
</html>
