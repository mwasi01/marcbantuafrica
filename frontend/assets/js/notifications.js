/**
 * Marcbantu Africa — Notifications helper.
 * The app.js already handles the topbar badge; this file is a placeholder
 * for a future dedicated notifications panel page.
 */
(function () {
    'use strict';
    // Reserved for a /notifications.html page in the future.
    if (window.UI?.Notifications?.updateBadge && window.Auth?.isLoggedIn()) {
        window.UI.Notifications.updateBadge();
    }
})();
