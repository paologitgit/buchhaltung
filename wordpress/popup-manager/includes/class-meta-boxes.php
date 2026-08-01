<?php
/**
 * Einstellungsformular im Popup-Editor.
 *
 * @package PopupManager
 */

namespace PopupManager;

defined( 'ABSPATH' ) || exit;

/**
 * Eine Meta-Box mit allen Popup-Einstellungen.
 */
class Meta_Boxes {

	/**
	 * Nonce-Feldname.
	 */
	const NONCE = 'pm_popup_nonce';

	/**
	 * Hooks registrieren.
	 */
	public function __construct() {
		add_action( 'add_meta_boxes', array( $this, 'register' ) );
		add_action( 'save_post_' . Plugin::POST_TYPE, array( $this, 'save' ), 10, 2 );
		add_action( 'admin_enqueue_scripts', array( $this, 'assets' ) );
	}

	/**
	 * Meta-Box registrieren.
	 *
	 * @return void
	 */
	public function register() {
		add_meta_box(
			'pm_popup_settings',
			__( 'Popup-Einstellungen', 'popup-manager' ),
			array( $this, 'render' ),
			Plugin::POST_TYPE,
			'normal',
			'high'
		);
	}

	/**
	 * Admin-Assets nur im Popup-Editor laden.
	 *
	 * @param string $hook Aktueller Admin-Screen.
	 * @return void
	 */
	public function assets( $hook ) {
		if ( ! in_array( $hook, array( 'post.php', 'post-new.php' ), true ) ) {
			return;
		}

		$screen = get_current_screen();

		if ( ! $screen || Plugin::POST_TYPE !== $screen->post_type ) {
			return;
		}

		wp_enqueue_style(
			'popup-manager-admin',
			PM_PLUGIN_URL . 'assets/css/admin.css',
			array(),
			PM_VERSION
		);

		wp_enqueue_script(
			'popup-manager-admin',
			PM_PLUGIN_URL . 'assets/js/admin.js',
			array(),
			PM_VERSION,
			true
		);
	}

	/**
	 * Formular ausgeben.
	 *
	 * @param \WP_Post $post Aktuelles Popup.
	 * @return void
	 */
	public function render( $post ) {
		wp_nonce_field( 'pm_save_popup', self::NONCE );

		$where          = Plugin::meta( $post->ID, 'where' );
		$include_ids    = Plugin::meta( $post->ID, 'include_ids' );
		$exclude_ids    = Plugin::meta( $post->ID, 'exclude_ids' );
		$delay          = Plugin::meta( $post->ID, 'delay' );
		$auto_close     = Plugin::meta( $post->ID, 'auto_close' );
		$close_button   = Plugin::meta( $post->ID, 'close_button' );
		$close_overlay  = Plugin::meta( $post->ID, 'close_overlay' );
		$frequency      = Plugin::meta( $post->ID, 'frequency' );
		$frequency_days = Plugin::meta( $post->ID, 'frequency_days' );
		$width          = Plugin::meta( $post->ID, 'width' );
		$max_height     = Plugin::meta( $post->ID, 'max_height' );
		$custom_css     = Plugin::meta( $post->ID, 'custom_css' );

		$where_options = array(
			'all'     => __( 'Auf der ganzen Website', 'popup-manager' ),
			'front'   => __( 'Nur auf der Startseite', 'popup-manager' ),
			'include' => __( 'Nur auf ausgewählten Seiten', 'popup-manager' ),
			'exclude' => __( 'Überall ausser auf ausgewählten Seiten', 'popup-manager' ),
		);
		?>
		<div class="pm-fields">

			<fieldset class="pm-section">
				<legend><?php esc_html_e( 'Wo soll das Popup erscheinen?', 'popup-manager' ); ?></legend>

				<?php foreach ( $where_options as $value => $label ) : ?>
					<label class="pm-radio">
						<input type="radio" name="pm_where" value="<?php echo esc_attr( $value ); ?>"
							<?php checked( $where, $value ); ?> data-pm-where>
						<?php echo esc_html( $label ); ?>
					</label>
				<?php endforeach; ?>

				<div class="pm-conditional" data-pm-when="include">
					<label for="pm_include_ids"><?php esc_html_e( 'Seiten auswählen', 'popup-manager' ); ?></label>
					<?php $this->render_post_select( 'pm_include_ids', $include_ids ); ?>
				</div>

				<div class="pm-conditional" data-pm-when="exclude">
					<label for="pm_exclude_ids"><?php esc_html_e( 'Seiten ausschliessen', 'popup-manager' ); ?></label>
					<?php $this->render_post_select( 'pm_exclude_ids', $exclude_ids ); ?>
				</div>
			</fieldset>

			<fieldset class="pm-section">
				<legend><?php esc_html_e( 'Erscheinen und Schliessen', 'popup-manager' ); ?></legend>

				<p class="pm-row">
					<label for="pm_delay"><?php esc_html_e( 'Anzeigen nach', 'popup-manager' ); ?></label>
					<input type="number" id="pm_delay" name="pm_delay" min="0" max="600" step="1"
						value="<?php echo esc_attr( $delay ); ?>" class="small-text">
					<span class="pm-unit"><?php esc_html_e( 'Sekunden (0 = sofort)', 'popup-manager' ); ?></span>
				</p>

				<p class="pm-row">
					<label for="pm_auto_close"><?php esc_html_e( 'Automatisch schliessen nach', 'popup-manager' ); ?></label>
					<input type="number" id="pm_auto_close" name="pm_auto_close" min="0" max="600" step="1"
						value="<?php echo esc_attr( $auto_close ); ?>" class="small-text">
					<span class="pm-unit"><?php esc_html_e( 'Sekunden (0 = nicht automatisch schliessen)', 'popup-manager' ); ?></span>
				</p>

				<p class="pm-row">
					<label class="pm-check">
						<input type="checkbox" name="pm_close_button" value="1" <?php checked( $close_button, 1 ); ?>>
						<?php esc_html_e( 'Schliessen-Button (×) anzeigen', 'popup-manager' ); ?>
					</label>
				</p>

				<p class="pm-row">
					<label class="pm-check">
						<input type="checkbox" name="pm_close_overlay" value="1" <?php checked( $close_overlay, 1 ); ?>>
						<?php esc_html_e( 'Klick auf den Hintergrund schliesst das Popup', 'popup-manager' ); ?>
					</label>
				</p>

				<p class="description">
					<?php esc_html_e( 'Die Optionen lassen sich kombinieren, zum Beispiel Schliessen-Button und zusätzlich automatisch nach 10 Sekunden. Ohne jede Schliessmöglichkeit wird der Schliessen-Button automatisch aktiviert.', 'popup-manager' ); ?>
				</p>
			</fieldset>

			<fieldset class="pm-section">
				<legend><?php esc_html_e( 'Wie oft pro Besucher?', 'popup-manager' ); ?></legend>

				<p class="pm-row">
					<select name="pm_frequency" id="pm_frequency" data-pm-frequency>
						<option value="always" <?php selected( $frequency, 'always' ); ?>>
							<?php esc_html_e( 'Bei jedem Seitenaufruf', 'popup-manager' ); ?>
						</option>
						<option value="session" <?php selected( $frequency, 'session' ); ?>>
							<?php esc_html_e( 'Einmal pro Besuch', 'popup-manager' ); ?>
						</option>
						<option value="days" <?php selected( $frequency, 'days' ); ?>>
							<?php esc_html_e( 'Einmal alle X Tage', 'popup-manager' ); ?>
						</option>
					</select>
				</p>

				<p class="pm-row pm-conditional" data-pm-when-frequency="days">
					<label for="pm_frequency_days"><?php esc_html_e( 'Abstand', 'popup-manager' ); ?></label>
					<input type="number" id="pm_frequency_days" name="pm_frequency_days" min="1" max="365" step="1"
						value="<?php echo esc_attr( $frequency_days ); ?>" class="small-text">
					<span class="pm-unit"><?php esc_html_e( 'Tage', 'popup-manager' ); ?></span>
				</p>

				<p class="description">
					<?php esc_html_e( 'Gemerkt wird im Browser des Besuchers. Wer Cookies und Browserdaten löscht, sieht das Popup erneut.', 'popup-manager' ); ?>
				</p>
			</fieldset>

			<fieldset class="pm-section">
				<legend><?php esc_html_e( 'Grösse', 'popup-manager' ); ?></legend>

				<p class="pm-row">
					<label for="pm_width"><?php esc_html_e( 'Breite', 'popup-manager' ); ?></label>
					<input type="number" id="pm_width" name="pm_width" min="200" max="2000" step="10"
						value="<?php echo esc_attr( $width ); ?>" class="small-text">
					<span class="pm-unit"><?php esc_html_e( 'Pixel', 'popup-manager' ); ?></span>
				</p>

				<p class="pm-row">
					<label for="pm_max_height"><?php esc_html_e( 'Maximale Höhe', 'popup-manager' ); ?></label>
					<input type="number" id="pm_max_height" name="pm_max_height" min="0" max="2000" step="10"
						value="<?php echo esc_attr( $max_height ); ?>" class="small-text">
					<span class="pm-unit"><?php esc_html_e( 'Pixel (0 = passt sich dem Inhalt an)', 'popup-manager' ); ?></span>
				</p>

				<p class="description">
					<?php esc_html_e( 'Das Popup ist immer mittig im Bildschirm. Auf schmalen Bildschirmen wird die Breite automatisch reduziert, damit nichts abgeschnitten wird.', 'popup-manager' ); ?>
				</p>
			</fieldset>

			<fieldset class="pm-section">
				<legend><?php esc_html_e( 'Eigenes CSS', 'popup-manager' ); ?></legend>

				<textarea name="pm_custom_css" id="pm_custom_css" rows="8" class="large-text code"
					spellcheck="false"><?php echo esc_textarea( $custom_css ); ?></textarea>

				<p class="description">
					<?php
					printf(
						/* translators: 1: CSS-Selektor des Popups, 2: CSS-Selektor des Inhalts. */
						esc_html__( 'Gilt nur für dieses Popup. Der Rahmen ist über %1$s erreichbar, der Inhalt über %2$s.', 'popup-manager' ),
						'<code>#pm-popup-' . (int) $post->ID . ' .pm-popup__box</code>',
						'<code>#pm-popup-' . (int) $post->ID . ' .pm-popup__content</code>'
					);
					?>
				</p>
			</fieldset>

			<?php if ( 'auto-draft' !== $post->post_status ) : ?>
				<p class="pm-row">
					<a class="button" target="_blank" rel="noopener"
						href="<?php echo esc_url( add_query_arg( 'pm_preview', $post->ID, home_url( '/' ) ) ); ?>">
						<?php esc_html_e( 'Vorschau auf der Website öffnen', 'popup-manager' ); ?>
					</a>
					<span class="description">
						<?php esc_html_e( 'Zeigt das Popup unabhängig von Platzierung und Häufigkeit. Nur für angemeldete Bearbeiter sichtbar.', 'popup-manager' ); ?>
					</span>
				</p>
			<?php endif; ?>

		</div>
		<?php
	}

	/**
	 * Mehrfachauswahl über Seiten und Beiträge.
	 *
	 * @param string $name    Feldname.
	 * @param string $current Kommagetrennte IDs.
	 * @return void
	 */
	private function render_post_select( $name, $current ) {
		$selected = array_filter( array_map( 'absint', explode( ',', (string) $current ) ) );

		$posts = get_posts(
			array(
				'post_type'        => array( 'page', 'post' ),
				'post_status'      => 'publish',
				'numberposts'      => 500,
				'orderby'          => 'title',
				'order'            => 'ASC',
				'suppress_filters' => false,
			)
		);
		?>
		<select name="<?php echo esc_attr( $name ); ?>[]" id="<?php echo esc_attr( $name ); ?>"
			multiple size="8" class="pm-post-select">
			<?php foreach ( $posts as $item ) : ?>
				<option value="<?php echo esc_attr( $item->ID ); ?>"
					<?php selected( in_array( (int) $item->ID, $selected, true ) ); ?>>
					<?php
					printf(
						'%s (%s, ID %d)',
						esc_html( get_the_title( $item ) ? get_the_title( $item ) : __( '(ohne Titel)', 'popup-manager' ) ),
						esc_html( 'page' === $item->post_type ? __( 'Seite', 'popup-manager' ) : __( 'Beitrag', 'popup-manager' ) ),
						(int) $item->ID
					);
					?>
				</option>
			<?php endforeach; ?>
		</select>
		<p class="description">
			<?php esc_html_e( 'Mehrfachauswahl mit gedrückter Strg- bzw. Cmd-Taste.', 'popup-manager' ); ?>
		</p>
		<?php
	}

	/**
	 * Formular speichern.
	 *
	 * @param int      $post_id Popup-ID.
	 * @param \WP_Post $post    Popup.
	 * @return void
	 */
	public function save( $post_id, $post ) {
		if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
			return;
		}

		if ( wp_is_post_revision( $post_id ) || wp_is_post_autosave( $post_id ) ) {
			return;
		}

		if ( ! isset( $_POST[ self::NONCE ] ) ) {
			return;
		}

		$nonce = sanitize_text_field( wp_unslash( $_POST[ self::NONCE ] ) );

		if ( ! wp_verify_nonce( $nonce, 'pm_save_popup' ) ) {
			return;
		}

		if ( ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}

		$values = array();

		foreach ( array_keys( Plugin::fields() ) as $key ) {
			$field = 'pm_' . $key;

			if ( ! isset( $_POST[ $field ] ) ) {
				// Nicht gesendete Checkboxen sind abgewählt, alle anderen
				// fehlenden Felder bekommen ihren Default.
				$values[ $key ] = Plugin::sanitize( $key, '' );
				continue;
			}

			$raw = wp_unslash( $_POST[ $field ] ); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput.InputNotSanitized -- Bereinigung erfolgt in Plugin::sanitize().

			if ( is_array( $raw ) ) {
				$raw = implode( ',', $raw );
			}

			$values[ $key ] = Plugin::sanitize( $key, $raw );
		}

		// Ein Popup muss schliessbar bleiben.
		if ( ! $values['close_button'] && ! $values['close_overlay'] && $values['auto_close'] < 1 ) {
			$values['close_button'] = 1;
		}

		foreach ( $values as $key => $value ) {
			update_post_meta( $post_id, Plugin::META_PREFIX . $key, $value );
		}
	}
}
