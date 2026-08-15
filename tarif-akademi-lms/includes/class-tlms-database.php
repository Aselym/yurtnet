<?php
/**
 * TLMS_Database
 *
 * Eklentinin ozel veritabani tablolarinin adlarini, semasini ve sabit
 * ders havuzunu tek bir yerden yonetir. Diger siniflar tablo isimlerine
 * her zaman bu sinif uzerinden erismelidir (dogrudan string yazmak yerine).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class TLMS_Database {

	/**
	 * Sistemde eslestirme yapilabilecek sabit ders havuzu.
	 * Ileriki adimlarda (ogretmen/ogrenci paneli) bu liste referans alinacak.
	 *
	 * @return string[]
	 */
	public static function get_subjects() {
		return array(
			'TYT Matematik',
			'TYT Sosyal',
			'TYT Turkce',
			'TYT Fen',
			'AYT Geometri',
			'AYT Matematik',
			'AYT Fizik',
			'AYT Kimya',
			'AYT Biyoloji',
		);
	}

	/**
	 * Ogretmen <-> Ogrenci <-> Ders eslestirme tablosunun tam adi.
	 *
	 * @return string
	 */
	public static function matches_table() {
		global $wpdb;
		return $wpdb->prefix . 'tarif_matches';
	}

	/**
	 * Haftalik ders programi tablosunun tam adi.
	 *
	 * @return string
	 */
	public static function schedules_table() {
		global $wpdb;
		return $wpdb->prefix . 'tarif_schedules';
	}

	/**
	 * dbDelta ile calistirilacak CREATE TABLE ifadelerini dondurur.
	 * dbDelta'nin dogru parse edebilmesi icin bicimlendirme kurallarina
	 * (her sutun ayri satirda, PRIMARY KEY girintisiz vb.) uyulmustur.
	 *
	 * @return string[]
	 */
	public static function get_schema_sql() {
		global $wpdb;
		$charset_collate = $wpdb->get_charset_collate();

		$matches_table   = self::matches_table();
		$schedules_table = self::schedules_table();

		$sql = array();

		// wp_tarif_matches: bir ogretmenin bir ogrenciye hangi dersten
		// mentorluk verdigini tutar. Ayni ogretmen-ogrenci ikilisi
		// birden fazla derste eslesebilir (her biri ayri satir).
		$sql[] = "CREATE TABLE {$matches_table} (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			teacher_id BIGINT UNSIGNED NOT NULL,
			student_id BIGINT UNSIGNED NOT NULL,
			subject VARCHAR(50) NOT NULL,
			status VARCHAR(20) NOT NULL DEFAULT 'active',
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			PRIMARY KEY  (id),
			KEY teacher_id (teacher_id),
			KEY student_id (student_id),
			KEY status (status)
		) {$charset_collate};";

		// wp_tarif_schedules: bir eslestirmeye bagli haftalik ders saati.
		// match_id, matches_table.id'ye referans verir (foreign key
		// InnoDB'de dbDelta ile guvenilir kurulmadigindan uygulama
		// katmaninda tutarlilik saglanir).
		$sql[] = "CREATE TABLE {$schedules_table} (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			match_id BIGINT UNSIGNED NOT NULL,
			day_of_week TINYINT UNSIGNED NOT NULL,
			start_time TIME NOT NULL,
			end_time TIME NOT NULL,
			status VARCHAR(20) NOT NULL DEFAULT 'active',
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			PRIMARY KEY  (id),
			KEY match_id (match_id),
			KEY status (status)
		) {$charset_collate};";

		return $sql;
	}
}
