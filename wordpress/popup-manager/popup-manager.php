<?php
/**
 * Plugin Name:       Popup Manager
 * Description:       Einfache Popups: Inhalt aus dem Editor (Text und Bilder), frei wählbare Seiten, Grösse, Verzögerung, Schliessen per Klick oder Zeit und eigenes CSS. Immer mittig im Bildschirm.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            Popup Manager
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       popup-manager
 * Domain Path:       /languages
 *
 * @package PopupManager
 */

defined( 'ABSPATH' ) || exit;

define( 'PM_VERSION', '1.0.0' );
define( 'PM_PLUGIN_FILE', __FILE__ );
define( 'PM_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'PM_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

/**
 * Autoloader für die Plugin-Klassen.
 *
 * PopupManager\Meta_Boxes  ->  includes/class-meta-boxes.php
 *
 * @param string $class Vollqualifizierter Klassenname.
 * @return void
 */
spl_autoload_register(
	function ( $class ) {
		if ( 0 !== strpos( $class, 'PopupManager\\' ) ) {
			return;
		}

		$name = substr( $class, strlen( 'PopupManager\\' ) );
		$name = strtolower( str_replace( '_', '-', $name ) );
		$file = PM_PLUGIN_DIR . 'includes/class-' . $name . '.php';

		if ( is_readable( $file ) ) {
			require_once $file;
		}
	}
);

/**
 * Zentrale Plugin-Instanz.
 *
 * @return \PopupManager\Plugin
 */
function popup_manager() {
	return \PopupManager\Plugin::instance();
}

popup_manager();

register_activation_hook(
	__FILE__,
	array( '\PopupManager\Plugin', 'activate' )
);

register_deactivation_hook(
	__FILE__,
	array( '\PopupManager\Plugin', 'deactivate' )
);
