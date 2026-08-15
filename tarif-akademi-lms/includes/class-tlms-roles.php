<?php
/**
 * TLMS_Roles
 *
 * Ozel kullanici rollerini tanimlar ve bu rollerin WP admin ile hicbir
 * temasi olmamasini saglar: admin bar gizlenir, wp-admin'e dogrudan
 * erisim engellenir, her sey site on yuzundeki (frontend) panellerde
 * gerceklesir.
 *
 * Moderator ayri bir custom role DEGILDIR; spesifikasyon geregi
 * moderator = WordPress'in kendi "administrator" rolune sahip kullanici.
 * Boylece moderator zaten var olan wp-admin yetkilerini (Adim 2'de
 * eklenecek ozel ayarlar sayfasi dahil) sorunsuz kullanir.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class TLMS_Roles {

	// Rol slug'lari - kod icinde string tekrarini onlemek icin sabit.
	const STUDENT = 'tarif_ogrenci';
	const TEACHER = 'tarif_ogretmen';

	// Ogretmen hesap durumu icin kullanilan user meta anahtari.
	// Degerler: 'pending' (onay bekliyor), 'active' (onayli), 'rejected' (reddedildi).
	const STATUS_META_KEY = 'tlms_status';

	public function __construct() {
		add_action( 'init', array( $this, 'maybe_hide_admin_bar' ) );
		add_action( 'admin_init', array( $this, 'block_wp_admin_access' ) );
		add_action( 'user_register', array( $this, 'set_default_status_on_register' ), 10, 1 );
	}

	/**
	 * "Ogrenci" custom rolunu WordPress'e kaydeder.
	 * Bu rol yalnizca site on yuzunu (kendi panelini) kullanabilir,
	 * hicbir wp-admin yetkisi tasimaz.
	 */
	public static function register_student_role() {
		remove_role( self::STUDENT ); // Onceki tanimi temizleyip guncel haliyle yeniden ekle.
		add_role(
			self::STUDENT,
			__( 'Ogrenci', 'tarif-lms' ),
			array(
				'read'    => true,  // Sadece kendi profiline / frontend'e erisim icin gerekli minimum yetki.
				'level_0' => true,
			)
		);
	}

	/**
	 * "Ogretmen/Koc" custom rolunu WordPress'e kaydeder.
	 */
	public static function register_teacher_role() {
		remove_role( self::TEACHER );
		add_role(
			self::TEACHER,
			__( 'Ogretmen', 'tarif-lms' ),
			array(
				'read'         => true,
				'upload_files' => true, // Ogrencilere PDF/ders notu yukleyebilmesi icin (Adim 6).
				'level_0'      => true,
			)
		);
	}

	/**
	 * Verilen kullanicinin (ya da giriş yapmis kullanicinin) ogrenci olup
	 * olmadigini kontrol eder.
	 *
	 * @param WP_User|int|null $user
	 * @return bool
	 */
	public static function is_student( $user = null ) {
		return self::user_has_role( $user, self::STUDENT );
	}

	/**
	 * Verilen kullanicinin ogretmen olup olmadigini kontrol eder.
	 *
	 * @param WP_User|int|null $user
	 * @return bool
	 */
	public static function is_teacher( $user = null ) {
		return self::user_has_role( $user, self::TEACHER );
	}

	/**
	 * Verilen kullanicinin moderator (= WP administrator) olup olmadigini
	 * kontrol eder.
	 *
	 * @param WP_User|int|null $user
	 * @return bool
	 */
	public static function is_moderator( $user = null ) {
		$user = self::resolve_user( $user );
		return $user instanceof WP_User && $user->exists() && $user->has_cap( 'manage_options' );
	}

	/**
	 * Bir ogretmen hesabinin onay durumunu dondurur.
	 * Ogrenci hesaplari icin her zaman 'active' kabul edilir (onay gerekmez).
	 *
	 * @param WP_User|int|null $user
	 * @return string 'active' | 'pending' | 'rejected'
	 */
	public static function get_status( $user = null ) {
		$user = self::resolve_user( $user );
		if ( ! $user instanceof WP_User || ! $user->exists() ) {
			return 'active';
		}

		if ( ! self::is_teacher( $user ) ) {
			return 'active';
		}

		$status = get_user_meta( $user->ID, self::STATUS_META_KEY, true );
		return $status ? $status : 'pending';
	}

	/**
	 * Yeni kayit olan kullaniciya varsayilan durum atar:
	 * - Ogretmen ise 'pending' (moderator onayi bekler, bkz. Adim 2).
	 * - Ogrenci ise 'active' (onay gerekmez).
	 *
	 * @param int $user_id
	 */
	public function set_default_status_on_register( $user_id ) {
		$user = get_userdata( $user_id );
		if ( ! $user ) {
			return;
		}

		if ( in_array( self::TEACHER, (array) $user->roles, true ) ) {
			// Zaten bir durum atanmamissa varsayilan olarak "onay bekliyor" yap.
			if ( ! get_user_meta( $user_id, self::STATUS_META_KEY, true ) ) {
				update_user_meta( $user_id, self::STATUS_META_KEY, 'pending' );
			}
		} elseif ( in_array( self::STUDENT, (array) $user->roles, true ) ) {
			update_user_meta( $user_id, self::STATUS_META_KEY, 'active' );
		}
	}

	/**
	 * Ogrenci/Ogretmen rollerindeki kullanicilar icin ust admin cubugunu
	 * (admin bar) tamamen kaldirir. Bu kullanicilar sadece frontend
	 * panellerini gormeli, WP admin'e ait hicbir iz gormemelidir.
	 */
	public function maybe_hide_admin_bar() {
		if ( ! is_user_logged_in() ) {
			return;
		}

		if ( self::is_student() || self::is_teacher() ) {
			add_filter( 'show_admin_bar', '__return_false' );
		}
	}

	/**
	 * Ogrenci/Ogretmen rollerindeki kullanicilarin wp-admin'e dogrudan URL
	 * ile erismesini engeller; kendi paneline geri yonlendirir.
	 *
	 * AJAX (admin-ajax.php) ve admin-post.php istekleri is_admin() = true
	 * dondurdugu icin bunlar bilerek disarida birakilir, aksi halde
	 * eklentinin kendi AJAX/form islemleri de bloklanirdi.
	 */
	public function block_wp_admin_access() {
		if ( wp_doing_ajax() ) {
			return;
		}

		// admin-post.php uzerinden calisan ozel form islemlerine (giris vb.) izin ver.
		if ( isset( $GLOBALS['pagenow'] ) && 'admin-post.php' === $GLOBALS['pagenow'] ) {
			return;
		}

		if ( ! is_user_logged_in() ) {
			return;
		}

		if ( self::is_moderator() ) {
			return; // Moderatorler (administrator) icin kisitlama yok.
		}

		if ( self::is_student() ) {
			wp_safe_redirect( home_url( '/' . TLMS_STUDENT_PANEL_SLUG . '/' ) );
			exit;
		}

		if ( self::is_teacher() ) {
			wp_safe_redirect( home_url( '/' . TLMS_TEACHER_PANEL_SLUG . '/' ) );
			exit;
		}
	}

	/**
	 * Verilen parametreyi WP_User nesnesine cevirir.
	 * null verilirse mevcut oturum sahibi kullanici alinir.
	 *
	 * @param WP_User|int|null $user
	 * @return WP_User|false
	 */
	private static function resolve_user( $user ) {
		if ( null === $user ) {
			return wp_get_current_user();
		}
		if ( $user instanceof WP_User ) {
			return $user;
		}
		return get_userdata( (int) $user );
	}

	/**
	 * Kullanicinin belirli bir role sahip olup olmadigini kontrol eden
	 * ortak yardimci fonksiyon.
	 *
	 * @param WP_User|int|null $user
	 * @param string           $role
	 * @return bool
	 */
	private static function user_has_role( $user, $role ) {
		$user = self::resolve_user( $user );
		if ( ! $user instanceof WP_User || ! $user->exists() ) {
			return false;
		}
		return in_array( $role, (array) $user->roles, true );
	}
}
