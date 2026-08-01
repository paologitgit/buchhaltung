<?php
/**
 * Aufräumen beim Löschen des Plugins.
 *
 * Wird nur ausgeführt, wenn das Plugin über "Plugins → Löschen" entfernt
 * wird, nicht beim blossen Deaktivieren.
 *
 * @package PopupManager
 */

defined( 'WP_UNINSTALL_PLUGIN' ) || exit;

$pm_popups = get_posts(
	array(
		'post_type'        => 'pm_popup',
		'post_status'      => 'any',
		'numberposts'      => -1,
		'fields'           => 'ids',
		'suppress_filters' => true,
	)
);

foreach ( $pm_popups as $pm_popup_id ) {
	// true = endgültig löschen, die zugehörigen Meta-Werte räumt
	// WordPress dabei selbst weg.
	wp_delete_post( $pm_popup_id, true );
}
