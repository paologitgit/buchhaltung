<?php
/**
 * Registriert den Post Type "Popups".
 *
 * @package PopupManager
 */

namespace PopupManager;

defined( 'ABSPATH' ) || exit;

/**
 * Popups werden wie Beiträge verwaltet: Titel als interne Bezeichnung,
 * Editor als Inhalt (Text und Bilder).
 */
class Post_Type {

	/**
	 * Hooks registrieren.
	 */
	public function __construct() {
		add_action( 'init', array( $this, 'register' ) );
		add_filter( 'manage_' . Plugin::POST_TYPE . '_posts_columns', array( $this, 'columns' ) );
		add_action( 'manage_' . Plugin::POST_TYPE . '_posts_custom_column', array( $this, 'column_content' ), 10, 2 );
		add_filter( 'post_row_actions', array( $this, 'row_actions' ), 10, 2 );
		add_filter( 'enter_title_here', array( $this, 'title_placeholder' ), 10, 2 );
	}

	/**
	 * Post Type registrieren.
	 *
	 * @return void
	 */
	public function register() {
		$labels = array(
			'name'               => __( 'Popups', 'popup-manager' ),
			'singular_name'      => __( 'Popup', 'popup-manager' ),
			'add_new'            => __( 'Erstellen', 'popup-manager' ),
			'add_new_item'       => __( 'Neues Popup', 'popup-manager' ),
			'edit_item'          => __( 'Popup bearbeiten', 'popup-manager' ),
			'new_item'           => __( 'Neues Popup', 'popup-manager' ),
			'view_item'          => __( 'Popup ansehen', 'popup-manager' ),
			'search_items'       => __( 'Popups durchsuchen', 'popup-manager' ),
			'not_found'          => __( 'Keine Popups vorhanden', 'popup-manager' ),
			'not_found_in_trash' => __( 'Keine Popups im Papierkorb', 'popup-manager' ),
			'all_items'          => __( 'Alle Popups', 'popup-manager' ),
			'menu_name'          => __( 'Popups', 'popup-manager' ),
		);

		register_post_type(
			Plugin::POST_TYPE,
			array(
				'labels'          => $labels,
				'public'          => false,
				'show_ui'         => true,
				'show_in_menu'    => true,
				'menu_position'   => 26,
				'menu_icon'       => 'dashicons-external',
				'supports'        => array( 'title', 'editor', 'revisions' ),
				'has_archive'     => false,
				'rewrite'         => false,
				'query_var'       => false,
				'capability_type' => 'page',
				'map_meta_cap'    => true,
				// Der Block-Editor kennt die Meta-Box-Felder nicht; der
				// klassische Editor hält das Formular in einem Screen.
				'show_in_rest'    => false,
			)
		);
	}

	/**
	 * Platzhalter im Titelfeld.
	 *
	 * @param string   $text Standardtext.
	 * @param \WP_Post $post Aktueller Beitrag.
	 * @return string
	 */
	public function title_placeholder( $text, $post ) {
		if ( $post && Plugin::POST_TYPE === $post->post_type ) {
			return __( 'Interne Bezeichnung, z. B. "Newsletter Startseite"', 'popup-manager' );
		}

		return $text;
	}

	/**
	 * Spalten der Übersichtsliste.
	 *
	 * @param array $columns Bestehende Spalten.
	 * @return array
	 */
	public function columns( $columns ) {
		$new = array();

		foreach ( $columns as $key => $label ) {
			$new[ $key ] = $label;

			if ( 'title' === $key ) {
				$new['pm_where'] = __( 'Anzeige auf', 'popup-manager' );
				$new['pm_time']  = __( 'Zeitverhalten', 'popup-manager' );
			}
		}

		return $new;
	}

	/**
	 * Inhalt der eigenen Spalten.
	 *
	 * @param string $column  Spalten-Key.
	 * @param int    $post_id Popup-ID.
	 * @return void
	 */
	public function column_content( $column, $post_id ) {
		if ( 'pm_where' === $column ) {
			echo esc_html( $this->describe_where( $post_id ) );
			return;
		}

		if ( 'pm_time' === $column ) {
			echo esc_html( $this->describe_timing( $post_id ) );
		}
	}

	/**
	 * Lesbare Beschreibung der Platzierung.
	 *
	 * @param int $post_id Popup-ID.
	 * @return string
	 */
	private function describe_where( $post_id ) {
		$where = Plugin::meta( $post_id, 'where' );

		switch ( $where ) {
			case 'front':
				return __( 'Nur Startseite', 'popup-manager' );

			case 'include':
				$ids = Plugin::meta( $post_id, 'include_ids' );

				return $ids
					? sprintf( __( 'Seiten: %s', 'popup-manager' ), $ids )
					: __( 'Keine Seite ausgewählt', 'popup-manager' );

			case 'exclude':
				$ids = Plugin::meta( $post_id, 'exclude_ids' );

				return $ids
					? sprintf( __( 'Überall ausser: %s', 'popup-manager' ), $ids )
					: __( 'Ganze Website', 'popup-manager' );

			default:
				return __( 'Ganze Website', 'popup-manager' );
		}
	}

	/**
	 * Lesbare Beschreibung von Verzögerung und Schliessverhalten.
	 *
	 * @param int $post_id Popup-ID.
	 * @return string
	 */
	private function describe_timing( $post_id ) {
		$delay      = Plugin::meta( $post_id, 'delay' );
		$auto_close = Plugin::meta( $post_id, 'auto_close' );

		$parts = array();

		$parts[] = $delay > 0
			/* translators: %d: Sekunden. */
			? sprintf( __( 'nach %d s', 'popup-manager' ), $delay )
			: __( 'sofort', 'popup-manager' );

		if ( $auto_close > 0 ) {
			/* translators: %d: Sekunden. */
			$parts[] = sprintf( __( 'schliesst nach %d s', 'popup-manager' ), $auto_close );
		}

		if ( Plugin::meta( $post_id, 'close_button' ) ) {
			$parts[] = __( 'mit Schliessen-Button', 'popup-manager' );
		}

		return implode( ', ', $parts );
	}

	/**
	 * Vorschau-Link in der Zeilenaktion der Übersicht.
	 *
	 * @param array    $actions Bestehende Aktionen.
	 * @param \WP_Post $post    Aktueller Beitrag.
	 * @return array
	 */
	public function row_actions( $actions, $post ) {
		if ( Plugin::POST_TYPE !== $post->post_type || ! current_user_can( 'edit_post', $post->ID ) ) {
			return $actions;
		}

		unset( $actions['inline hide-if-js'] );

		$actions['pm_preview'] = sprintf(
			'<a href="%s" target="_blank" rel="noopener">%s</a>',
			esc_url( add_query_arg( 'pm_preview', $post->ID, home_url( '/' ) ) ),
			esc_html__( 'Vorschau', 'popup-manager' )
		);

		return $actions;
	}
}
