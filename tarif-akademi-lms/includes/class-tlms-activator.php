<?php
/**
 * TLMS_Activator
 *
 * Eklenti etkinlestirildiginde/devre disi birakildiginda calisan
 * kurulum ve temizlik mantigini icerir.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class TLMS_Activator {

	/**
	 * Eklenti etkinlestirildiginde:
	 * 1) Ozel veritabani tablolarini olusturur (dbDelta).
	 * 2) Ogrenci/Ogretmen rollerini kaydeder.
	 *
	 * Not: Moderator icin ayri bir rol OLUSTURULMAZ; mevcut
	 * "administrator" rolu moderator olarak kullanilir.
	 */
	public static function activate() {
		self::create_tables();

		TLMS_Roles::register_student_role();
		TLMS_Roles::register_teacher_role();

		update_option( 'tlms_db_version', TLMS_VERSION );

		flush_rewrite_rules();
	}

	/**
	 * Eklenti devre disi birakildiginda calisir.
	 * Kasitli olarak veritabani tablolarina VE rollere DOKUNULMAZ:
	 * eklenti gecici olarak kapatilirsa mevcut eslestirme/program
	 * verileri kaybolmamali. Kalici silme islemi (uninstall) ayri
	 * bir uninstall.php dosyasinda, acikca istenirse ele alinacaktir.
	 */
	public static function deactivate() {
		flush_rewrite_rules();
	}

	/**
	 * TLMS_Database::get_schema_sql() ile tanimlanan tablolari dbDelta
	 * kullanarak olusturur/gunceller. dbDelta hem ilk kurulumda hem de
	 * sema degisikliklerinde guvenle tekrar calistirilabilir.
	 */
	private static function create_tables() {
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';

		foreach ( TLMS_Database::get_schema_sql() as $sql ) {
			dbDelta( $sql );
		}
	}
}
