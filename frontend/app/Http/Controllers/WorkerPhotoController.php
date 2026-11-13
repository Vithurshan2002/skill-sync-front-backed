<?php

namespace App\Http\Controllers;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Http;

class WorkerPhotoController extends Controller
{
    public function __invoke(string $key): Response
    {
        try {
            $photo = Http::baseUrl(rtrim(config('skillsync.fastapi_base_url'), '/'))
                ->connectTimeout(config('skillsync.connect_timeout'))->timeout(config('skillsync.timeout'))
                ->get('/api/v1/worker-photos/'.$key.'.jpg');
        } catch (ConnectionException) {
            abort(503);
        }
        abort_if($photo->status() === 404, 404);
        abort_unless($photo->successful() && str_starts_with($photo->header('Content-Type'), 'image/jpeg'), 503);

        return response($photo->body(), 200, [
            'Content-Type' => 'image/jpeg', 'X-Content-Type-Options' => 'nosniff',
            'Cache-Control' => 'no-cache',
        ]);
    }
}
